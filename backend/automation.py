from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any, cast

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from backend.config import get_settings
from backend.resume import ResumeEngine


class ATSAdapter(ABC):
    name: str

    @abstractmethod
    async def detect_fields(self, page: Page) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def fill(self, page: Page, values: Mapping[str, str]) -> None:
        raise NotImplementedError


class GenericATSAdapter(ATSAdapter):
    def __init__(self, name: str) -> None:
        self.name = name

    async def detect_fields(self, page: Page) -> list[dict[str, Any]]:
        fields = await page.locator("input, textarea, select").evaluate_all(
            "els => els.map(el => ({name: el.name, label: el.getAttribute('aria-label'), type: el.type}))"
        )
        return cast(list[dict[str, Any]], fields)

    async def fill(self, page: Page, values: Mapping[str, str]) -> None:
        fields = await self.detect_fields(page)
        for field in fields:
            name = str(field.get("name") or field.get("label") or "")
            if name in values:
                await page.locator(f'[name="{name}"]').fill(values[name])


class ATSApplicationAutomation:
    def __init__(self) -> None:
        self._playwright: Any = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def _get_page(self) -> Page:
        if self._playwright is None or self._context is None or self._context.browser is None or not self._context.browser.is_connected():
            if self._playwright is not None:
                await self._playwright.stop()
            self._playwright = await async_playwright().start()
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(Path(get_settings().browser_profile_dir) / "ats"),
                headless=False,
                channel="msedge",
                viewport={"width": 1440, "height": 1000},
            )
            self._page = None
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
        return self._page

    async def prepare(self, job_url: str, values: Mapping[str, str], resume_path: str, submit: bool) -> dict[str, object]:
        tailored_resume = self._tailor_resume(resume_path, values.get("job_description", "")) if resume_path else resume_path
        page = await self._get_page()
        await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        await page.bring_to_front()
        body = (await page.locator("body").inner_text()).lower()
        if any(marker in body for marker in ("captcha", "verify you are human")):
            return {"status": "blocked", "reason": "CAPTCHA or bot verification requires your action.", "fields_filled": [], "fields_missing": []}

        values_by_hint = {
            "name": values.get("name", ""),
            "email": values.get("email", ""),
            "phone": values.get("phone", ""),
        }
        filled: list[str] = []
        missing: list[str] = []
        fields = page.locator("input, textarea, select")
        for index in range(await fields.count()):
            field = fields.nth(index)
            field_type = (await field.get_attribute("type") or "text").lower()
            if field_type in {"hidden", "submit", "button", "radio"}:
                continue
            descriptor = " ".join(filter(None, [await field.get_attribute("name"), await field.get_attribute("id"), await field.get_attribute("placeholder"), await field.get_attribute("aria-label")])).lower()
            matched_key = next((key for key in values_by_hint if key in descriptor), None)
            if field_type == "file" and resume_path:
                await field.set_input_files(tailored_resume)
                filled.append("resume")
            elif field_type == "checkbox" and await field.get_attribute("required") is not None:
                missing.append(descriptor or f"required consent {index + 1}")
            elif matched_key and values_by_hint[matched_key]:
                await field.fill(values_by_hint[matched_key])
                filled.append(matched_key)
            elif await field.get_attribute("required") is not None:
                missing.append(descriptor or f"required field {index + 1}")

        if submit and missing:
            return {"status": "review_required", "reason": "The form has required fields that could not be answered truthfully, so submission was stopped.", "fields_filled": sorted(set(filled)), "fields_missing": sorted(set(missing))}
        if submit:
            submit_control = page.get_by_role("button", name=re.compile(r"apply|submit|send", re.IGNORECASE)).last
            if await submit_control.count() == 0:
                submit_control = page.locator("input[type=submit], button[type=submit]").last
            if await submit_control.count() == 0:
                return {"status": "review_required", "reason": "All recognized fields were filled, but no unambiguous submit control was found.", "fields_filled": sorted(set(filled)), "fields_missing": []}
            await submit_control.click()
            await page.wait_for_timeout(1500)
            confirmation_text = (await page.locator("body").inner_text()).casefold()
            confirmation_markers = ("application submitted", "application received", "thank you for applying", "thanks for applying", "successfully applied")
            if not any(marker in confirmation_text for marker in confirmation_markers):
                return {"status": "review_required", "reason": "The form control was clicked, but the employer did not show a submission confirmation. Check the browser before treating this as submitted.", "fields_filled": sorted(set(filled)), "fields_missing": []}
            return {"status": "submitted", "reason": "The employer page confirmed that the application was submitted.", "fields_filled": sorted(set(filled)), "fields_missing": []}
        return {"status": "ready_for_review", "reason": "The real employer form is open and known fields are filled. Review it in the browser before submitting.", "fields_filled": sorted(set(filled)), "fields_missing": sorted(set(missing))}

    def _tailor_resume(self, resume_path: str, job_description: str) -> str:
        source = Path(resume_path)
        if not source.exists() or source.suffix.lower() != ".docx":
            return resume_path
        terms = re.findall(r"\b(?:python|sql|tensorflow|pytorch|fastapi|flask|opencv|nlp|rag|langchain|\w+\s+engineering|machine learning|data analysis|generative ai)\b", job_description.lower())
        keywords = list(dict.fromkeys(term.title() for term in terms))[:20]
        output_dir = Path(".generated-resumes")
        output_dir.mkdir(exist_ok=True)
        output = output_dir / f"{source.stem}-tailored.docx"
        ResumeEngine().tailor(source, output, output.with_suffix(".pdf"), keywords)
        return str(output)


class BrowserManager:
    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._playwright: Any = None
        self.browser: Browser | None = None

    async def __aenter__(self) -> BrowserContext:
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        return await self.browser.new_context()

    async def __aexit__(self, *_: object) -> None:
        if self.browser is not None:
            await self.browser.close()
        if self._playwright is not None:
            await self._playwright.stop()


class NaukriAutomation:
    base_url = "https://www.naukri.com"
    login_url = "https://www.naukri.com/nlogin/login"
    _playwright: Any = None
    _browser_context: BrowserContext | None = None
    _page: Page | None = None

    def _search_url(self, role: str, location: str) -> str:
        role_slug = "-".join(role.lower().split())
        if location:
            location_slug = "-".join(location.lower().split())
            return f"{self.base_url}/{role_slug}-jobs-in-{location_slug}"
        return f"{self.base_url}/{role_slug}-jobs"

    async def _get_context(self) -> tuple[Any, BrowserContext]:
        browser_disconnected = self.browser_is_disconnected()
        if self._playwright is None or self._browser_context is None or browser_disconnected:
            if self._playwright is not None:
                await self._playwright.stop()
            self._playwright = None
            self._browser_context = None
            self._playwright = await async_playwright().start()
            self._browser_context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(Path(get_settings().browser_profile_dir)),
                headless=False,
                channel="msedge",
                viewport={"width": 1440, "height": 1000},
            )
        return self._playwright, self._browser_context

    def browser_is_disconnected(self) -> bool:
        if self._browser_context is None:
            return False
        browser = self._browser_context.browser
        return browser is None or not browser.is_connected()

    async def check_login_status(self) -> dict[str, Any]:
        if self._browser_context is None or self.browser_is_disconnected():
            return {"open": False, "logged_in": False, "message": "Browser is not open. Launch browser to log in."}
        
        pages = self._browser_context.pages
        if not pages:
            return {"open": True, "logged_in": False, "message": "Browser is open with no active tabs."}
            
        page = self._page if (self._page and not self._page.is_closed()) else pages[-1]
        self._page = page

        try:
            url = page.url
            body = (await page.locator("body").inner_text()).lower()
            title = await page.title()

            is_logged_in = False
            user_name = ""

            if "mnjuser" in url or "homepage" in url or "my-naukri" in url:
                is_logged_in = True
            elif any(marker in body for marker in ("my naukri", "view profile", "update profile", "my profile", "edit profile")):
                if not ("nlogin" in url or "register" in url):
                    is_logged_in = True

            # Attempt to discover candidate name from profile badge
            profile_name_locator = page.locator(".nI-gNb-drawer__user-details .nI-gNb-header__user-name, .user-name, .user-profile").first
            if await profile_name_locator.count() > 0:
                user_name = (await profile_name_locator.inner_text()).strip()
                is_logged_in = True

            return {
                "open": True,
                "logged_in": is_logged_in,
                "user_name": user_name or ("Logged In User" if is_logged_in else ""),
                "current_url": url,
                "title": title,
                "message": f"Logged in to Naukri ({user_name})" if user_name else ("Logged in to Naukri" if is_logged_in else "Browser open. Please log in on the browser window."),
            }
        except Exception as error:
            return {"open": True, "logged_in": False, "message": f"Checking status: {error}"}

    async def open(self) -> dict[str, str]:
        try:
            _, context = await self._get_context()
            if self._page is None or self._page.is_closed():
                self._page = await context.new_page()
            await self._page.goto(self.login_url, wait_until="domcontentloaded", timeout=60000)
            await self._page.bring_to_front()
            return {"status": "browser_open", "reason": "Log in to Naukri in the visible browser, then click Search Naukri again."}
        except Exception as error:
            self._page = None
            return {"status": "browser_error", "reason": f"Naukri browser could not open: {error}"}

    async def close(self) -> dict[str, str]:
        if self._browser_context is not None:
            await self._browser_context.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._page = None
        self._browser_context = None
        self._playwright = None
        return {"status": "browser_closed", "reason": "Naukri browser session closed."}

    async def search(self, roles: list[str], locations: list[str], max_pages: int | None = None) -> dict[str, Any]:
        await self.open()
        page = self._page
        if page is None:
            return {"status": "browser_error", "reason": "Could not create the Naukri browser page.", "jobs": []}
        try:
            jobs: list[dict[str, str]] = []
            pages = max_pages or get_settings().naukri_max_pages
            for role in roles:
                for location in locations or [""]:
                    for page_number in range(1, pages + 1):
                        await page.goto(self._search_url(role, location), wait_until="domcontentloaded", timeout=60000)
                        if page_number > 1:
                            await page.goto(f"{page.url}{'&' if '?' in page.url else '?'}page={page_number}", wait_until="domcontentloaded", timeout=60000)
                        body = (await page.locator("body").inner_text()).lower()
                        if "captcha" in body or "verify you are human" in body:
                            return {"status": "blocked", "reason": "CAPTCHA or bot verification requires your action.", "jobs": jobs}
                        if "login" in page.url or "sign in" in body[:1000]:
                            return {"status": "login_required", "reason": "Log in to Naukri in the opened browser, then run the search again.", "jobs": jobs}
                        cards = page.locator("article.jobTuple, .srp-jobtuple-wrapper")
                        for index in range(await cards.count()):
                            card = cards.nth(index)
                            title_link = card.locator("a.title").first
                            if await title_link.count() == 0:
                                continue
                            jobs.append({
                                "title": (await title_link.inner_text()).strip(),
                                "application_url": await title_link.get_attribute("href") or "",
                                "company": (await card.locator(".comp-name").first.inner_text()).strip() if await card.locator(".comp-name").count() else "",
                                "location": (await card.locator(".locWdth").first.inner_text()).strip() if await card.locator(".locWdth").count() else location,
                                "description": (await card.locator(".job-desc").first.inner_text()).strip() if await card.locator(".job-desc").count() else "",
                                "source": "naukri",
                            })
            unique_jobs = {job["application_url"]: job for job in jobs if job["application_url"]}
            return {"status": "ready_for_review", "jobs": list(unique_jobs.values())}
        except Exception as error:
            return {"status": "browser_error", "reason": str(error), "jobs": []}

    async def apply(self, job_url: str, values: Mapping[str, str], approved: bool) -> dict[str, str]:
        if not approved:
            return {"status": "review_required", "reason": "Approval is required before submitting an application."}
        await self.open()
        page = self._page
        if page is None:
            return {"status": "browser_error", "reason": "Could not create the Naukri browser page."}
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            body = (await page.locator("body").inner_text()).lower()
            if "captcha" in body or "verify you are human" in body:
                return {"status": "blocked", "reason": "CAPTCHA or bot verification requires your action."}
            if "login" in page.url or "sign in" in body[:1000]:
                return {"status": "login_required", "reason": "Log in to Naukri in the opened browser first."}
            apply_button = page.get_by_text("Apply", exact=True).first
            if await apply_button.count() == 0:
                return {"status": "external_site", "reason": "This role has no Naukri easy-apply button; review the company site manually."}
            await apply_button.click()
            await GenericATSAdapter("naukri").fill(page, values)
            submit = page.get_by_text("Submit", exact=True).first
            if await submit.count() == 0:
                return {"status": "review_required", "reason": "Fields were prepared, but no unambiguous submit control was found."}
            await submit.click()
            return {"status": "submitted", "reason": "Naukri accepted the application submission."}
        except Exception as error:
            return {"status": "browser_error", "reason": str(error)}
