from __future__ import annotations

import os
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass

from .xmlutil import first_text, parse_items

PUBLICATION_SERVICE = "https://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice"
LEGACY_CITATION_SERVICE = "https://plus.kipris.or.kr/openapi/rest/CitationService"


class KiprisConfigError(RuntimeError):
    pass


@dataclass
class KiprisClient:
    publication_access_key: str | None = None
    citation_access_key: str | None = None
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "KiprisClient":
        common_key = os.getenv("KIPRIS_API_KEY")
        return cls(
            publication_access_key=os.getenv("KIPRIS_ACCESS_KEY") or common_key,
            citation_access_key=os.getenv("KIPRIS_ACCESS_KEY") or common_key,
        )

    @staticmethod
    def _get(url: str, params: dict[str, str], timeout: int) -> str:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{url}?{query}",
            headers={"User-Agent": "Team-GOAT-Patent-Evidence-PoC/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                try:
                    return raw.decode("utf-8")
                except UnicodeDecodeError:
                    # Some KIPRIS responses declare UTF-8 but contain Korean legacy bytes.
                    return raw.decode("cp949")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"KIPRIS HTTP {exc.code}; check API approval and operation") from None
        except urllib.error.URLError:
            raise RuntimeError("KIPRIS connection failed; check network and endpoint") from None

    def _publication_call(self, operation: str, **params: str) -> str:
        if not self.publication_access_key:
            raise KiprisConfigError("KIPRIS_API_KEY is not set")
        xml = self._get(
            f"{PUBLICATION_SERVICE}/{operation}",
            {**params, "accessKey": self.publication_access_key},
            self.timeout,
        )
        code = first_text(xml, ("resultCode",))
        if code and code not in {"0", "00"}:
            raise RuntimeError(f"KIPRIS publication API returned code {code}")
        return xml

    def search_application_xml(self, application_number: str) -> str:
        return self._publication_call(
            "applicationNumberSearchInfo",
            applicationNumber=application_number,
            patent="true",
            utility="false",
            docsStart="1",
            docsCount="10",
        )

    def search_application(self, application_number: str) -> list[dict[str, str]]:
        return parse_items(self.search_application_xml(application_number))

    def abstract_xml(self, application_number: str) -> str:
        return self._publication_call(
            "patentAbstractInfo",
            applicationNumber=application_number,
        )

    def claim_xml(self, application_number: str) -> str:
        return self._publication_call(
            "patentClaimInfo",
            applicationNumber=application_number,
        )

    def ipc_xml(self, application_number: str) -> str:
        return self._publication_call(
            "patentIpcInfo",
            applicationNumber=application_number,
        )

    def cpc_xml(self, application_number: str) -> str:
        return self._publication_call(
            "patentCpcInfo",
            applicationNumber=application_number,
        )

    def open_number_search_xml(self, open_number: str) -> str:
        return self._publication_call(
            "openNumberSearchInfo",
            openNumber=open_number,
            patent="true",
            utility="false",
            docsStart="1",
            docsCount="10",
        )

    def open_number_search(self, open_number: str) -> list[dict[str, str]]:
        return parse_items(self.open_number_search_xml(open_number))

    def registration_number_search_xml(self, register_number: str) -> str:
        return self._publication_call(
            "registrationNumberSearchInfo",
            registerNumber=register_number,
            patent="true",
            utility="false",
            docsStart="1",
            docsCount="10",
        )

    def registration_number_search(self, register_number: str) -> list[dict[str, str]]:
        return parse_items(self.registration_number_search_xml(register_number))

    def citation_xml(
        self,
        application_number: str,
        operation: str = "citationInfoV3",
    ) -> str:
        if not self.citation_access_key:
            raise KiprisConfigError("KIPRIS_ACCESS_KEY is not set")
        return self._get(
            f"{LEGACY_CITATION_SERVICE}/{operation}",
            {
                "applicationNumber": application_number,
                "accessKey": self.citation_access_key,
            },
            self.timeout,
        )
