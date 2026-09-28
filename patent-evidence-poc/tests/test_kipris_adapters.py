from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.patent_evidence.citations import citation_to_lookup
from src.patent_evidence.kipris import KiprisClient
from src.patent_evidence.dataset import (
    citation_division_counts,
    parse_domestic_citation_lookups,
    select_gold_candidates,
)
from src.patent_evidence.xmlutil import parse_items
from scripts.inspect_kipris_case import summarize_citations


class CitationMappingTests(unittest.TestCase):
    def test_open_publication_mapping(self):
        value = citation_to_lookup("KR", "A1", "10-2020-0012345")
        self.assertIsNotNone(value)
        self.assertEqual(value.lookup_kind, "open_number")
        self.assertEqual(value.lookup_value, "1020200012345")

    def test_registration_mapping(self):
        value = citation_to_lookup("KR", "B1", "10-1234567")
        self.assertIsNotNone(value)
        self.assertEqual(value.lookup_kind, "registration_number")
        self.assertEqual(value.lookup_value, "101234567")

    def test_foreign_is_excluded_from_korean_v1(self):
        self.assertIsNone(citation_to_lookup("US", "A1", "US123456"))

    def test_xml_parser_is_namespace_tolerant(self):
        xml = """<response xmlns="urn:test"><body><items><item>
        <applicationNumber>1020200000001</applicationNumber>
        <inventionTitle>테스트</inventionTitle>
        </item></items></body></response>"""
        rows = parse_items(xml)
        self.assertEqual(rows[0]["applicationNumber"], "1020200000001")
        self.assertEqual(rows[0]["inventionTitle"], "테스트")

    def test_live_response_row_names_are_parsed(self):
        publication = """<response><body><items><PatentUtilityInfo>
        <ApplicationNumber>1020140170841</ApplicationNumber>
        <InventionName>한국어 특허</InventionName>
        </PatentUtilityInfo></items></body></response>"""
        citation = """<response><body><items><citationInfoV3>
        <StandardCitationLiteratureCountryCode>KR</StandardCitationLiteratureCountryCode>
        <StandardCitationIdentificationCode>A</StandardCitationIdentificationCode>
        <StandardCitationLiteraturenumber>1020100093858</StandardCitationLiteraturenumber>
        <CitationLiteratureTypeCode>E0802</CitationLiteratureTypeCode>
        <CitationLiteratureTypeCodeName>선행기술조사보고서</CitationLiteratureTypeCodeName>
        </citationInfoV3></items></body></response>"""
        self.assertEqual(parse_items(publication)[0]["InventionName"], "한국어 특허")
        rows = parse_domestic_citation_lookups(citation)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["citation_division_code"], "E0802")
        self.assertEqual(
            select_gold_candidates(rows, allowed_division_codes={"E0802"})[0]["lookup_value"],
            "1020100093858",
        )

    def test_publication_search_uses_openapi_access_key(self):
        client = KiprisClient(publication_access_key="test-key")
        with patch.object(KiprisClient, "_get", return_value="<response><resultCode>00</resultCode></response>") as get:
            client.search_application_xml("1020140170841")
        url, params, _ = get.call_args.args
        self.assertIn("/openapi/rest/", url)
        self.assertEqual(params["accessKey"], "test-key")
        self.assertNotIn("ServiceKey", params)

    def test_citation_xml_preserves_division_and_excludes_foreign(self):
        xml = """<response><body><items>
        <item>
          <standardCitationLiteratureCountryCode>KR</standardCitationLiteratureCountryCode>
          <standardCitationIdentificationCode>A1</standardCitationIdentificationCode>
          <standardCitationLiteraturenumber>1020200012345</standardCitationLiteraturenumber>
          <standardCitationDivisionCodeName>EXAMINER_FINAL</standardCitationDivisionCodeName>
        </item>
        <item>
          <standardCitationLiteratureCountryCode>KR</standardCitationLiteratureCountryCode>
          <standardCitationIdentificationCode>B1</standardCitationIdentificationCode>
          <standardCitationLiteraturenumber>101234567</standardCitationLiteraturenumber>
          <standardCitationDivisionCodeName>APPLICANT</standardCitationDivisionCodeName>
        </item>
        <item>
          <standardCitationLiteratureCountryCode>US</standardCitationLiteratureCountryCode>
          <standardCitationIdentificationCode>A1</standardCitationIdentificationCode>
          <standardCitationLiteraturenumber>US123</standardCitationLiteraturenumber>
          <standardCitationDivisionCodeName>EXAMINER_FINAL</standardCitationDivisionCodeName>
        </item>
        </items></body></response>"""
        rows = parse_domestic_citation_lookups(xml)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            citation_division_counts(rows),
            {"APPLICANT": 1, "EXAMINER_FINAL": 1},
        )

        gold = select_gold_candidates(
            rows,
            allowed_division_names={"EXAMINER_FINAL"},
        )
        self.assertEqual(len(gold), 1)
        self.assertEqual(gold[0]["lookup_kind"], "open_number")

    def test_gold_policy_cannot_be_implicit(self):
        with self.assertRaises(ValueError):
            select_gold_candidates([], allowed_division_names=set())

    def test_inspection_exposes_raw_fields_and_division_distribution(self):
        xml = """<response><body><items><item>
        <standardCitationLiteratureCountryCode>KR</standardCitationLiteratureCountryCode>
        <standardCitationIdentificationCode>A1</standardCitationIdentificationCode>
        <standardCitationLiteratureNumber>1020200012345</standardCitationLiteratureNumber>
        <standardCitationDivisionCode>01</standardCitationDivisionCode>
        <standardCitationDivisionCodeName>sample-origin</standardCitationDivisionCodeName>
        </item></items></body></response>"""
        summary = summarize_citations(xml)
        self.assertEqual(summary["citation_item_count"], 1)
        self.assertIn("standardCitationDivisionCode", summary["citation_field_names"])
        self.assertEqual(
            summary["citation_divisions"],
            [{"code": "01", "name": "sample-origin", "count": 1}],
        )


if __name__ == "__main__":
    unittest.main()
