# This is a tool to extract form structures from an HTML file.
#
# The HTML file should be a dump of a website from Chrome with the
# chrome://flags/#show-autofill-type-predictions flag enabled to extract
# metadata about Chrome Autofill's interpretation of the form.
#
# You have to pass the language and country of the website:
# --country=EG   # for Egypt
# --language=ar  # for Arabic
# file.html      # the file from which we extract form controls
#
# If you pass --label-follows-field, the field labels extracted by Chrome
# are ignored and we take the text following form controls. For some websites
# this works better than Chrome's current label detection.
#
# If you pass --translate, all labels are translated via Google Translate.

import address_pb2
import argparse
import bs4
from bs4 import BeautifulSoup
from google.protobuf import text_format
from google.cloud import translate_v2 as translate


# If Chrome is started with chrome://flags/#show-autofill-type-predictions
# enabled, an autofill-information attribute of form controls contains
# information about Chrome autofill's interpretation of the form control.
def extract_autofill_information(element):
  if not element.has_attr("autofill-information"):
    return {}
  autofill_information = [
      row.strip() for row in element["autofill-information"].split("\n")
  ]
  autofill_information = [row.split(": ", 2) for row in autofill_information]
  autofill_information = [row for row in autofill_information if len(row) == 2]
  return {row[0]: row[1] for row in autofill_information}


# For some fields Chrome does not extract the label correctly today. This is
# an alternative strategy to discover labels by looking at the text after
# a form control. You can enable this strategy with the --label-follows-field
# command line parameter.
def extract_label_after_field(element):
  for attempt in range(1, 3):
    element = element.next_sibling
    if not element:
      return ""
    if element.string and element.string.strip():
      return element.string.strip()
    if isinstance(element, bs4.element.NavigableString) and element.strip():
      return element
    if not isinstance(element, bs4.element.NavigableString):
      contents = u' '.join(element.findAll(text=True)).strip()
      if contents:
        return contents
  return ""

def extract_label_before_field(element):
  for attempt in range(1, 3):
    element = element.previous_sibling
    if not element:
      return ""
    if element.string and element.string.strip():
      return element.string.strip()
    if isinstance(element, bs4.element.NavigableString) and element.strip():
      return element
    if not isinstance(element, bs4.element.NavigableString):
      contents = u' '.join(element.findAll(text=True)).strip()
      if contents:
        return contents
  return ""

parser = argparse.ArgumentParser(description="Extract fields of forms.")
parser.add_argument(
    "--country",
    type=str,
    metavar="cc",
    help="two-letter country code (eg. 'EN') as per ISO 3166-1",
    required=True,
)
parser.add_argument(
    "--language",
    type=str,
    metavar="ll",
    help="two-letter language code (e.g. 'en') as per ISO 639-1.",
    required=True,
)
parser.add_argument(
    "--label-follows-field",
    action="store_true",
    help="label follows field (in some languages or sites, the label of a field"
    " follow the field. In this case, chrome does a poor job at extracting"
    " the label.",
)
parser.add_argument(
    "--label-before-field",
    action="store_true",
    help="take label from dom predecessor",
)
parser.add_argument(
    "--translate", action="store_true", help="enable Google translate")
parser.add_argument(
    "file",
    type=str,
    metavar="file",
    help="HTML file from which to extract fields.",
)

args = parser.parse_args()

f = open(args.file, "rb")
soup = BeautifulSoup(f.read(), "html.parser")
f.close()

ontology = address_pb2.AddressOntology()
site_example = ontology.site_examples.add()
site_example.locale.country = args.country
site_example.locale.language = args.language
site_example.url = "todo"
site_example.is_structured = True

translate_client = translate.Client()

sequence = site_example.sequences.add()
sequence.section = address_pb2.ExampleSequenceSection.UNDEFINED
sequence.hide = False
for html_field in soup.find_all(["input", "select", "textarea"]):
  field = sequence.fields.add()
  field.name = ((html_field["id"] if html_field.has_attr("id") else "") + "|" +
                (html_field["name"] if html_field.has_attr("name") else ""))
  placeholder = (
      html_field["placeholder"] if html_field.has_attr("placeholder") else "")
  autocomplete = (
      html_field["autocomplete"] if html_field.has_attr("autocomplete") else "")

  autofill_information = extract_autofill_information(html_field)
  overall_type = autofill_information.get("overall type", "")

  if args.label_follows_field:
    field.label = extract_label_after_field(html_field)
  elif args.label_before_field:
    field.label = extract_label_before_field(html_field)
  else:
    field.label = autofill_information.get("label", "")
  if field.label and args.translate:
    translation = translate_client.translate(
        field.label, target_language="en", source_language=args.language)
    field.label_translated = translation["translatedText"]
  if placeholder and placeholder.strip():
    field.example = placeholder.strip()
    if field.example == field.label:
      field.example = ""
    if args.translate:
      translation = translate_client.translate(
          field.example, target_language="en", source_language=args.language)
      field.example_translated = translation["translatedText"]

  field.control_type = address_pb2.ControlType.UNSPECIFIED
  if html_field.name == "input":
    if html_field.has_attr("type") and html_field["type"] == "radio":
      field.control_type = address_pb2.ControlType.RADIO
    elif html_field.has_attr("type") and html_field["type"] == "checkbox":
      field.control_type = address_pb2.ControlType.CHECKBOX
    else:
      field.control_type = address_pb2.ControlType.INPUT
  elif html_field.name == "select":
    field.control_type = address_pb2.ControlType.SELECT
  elif html_field.name == "textarea":
    field.control_type = address_pb2.ControlType.TEXTAREA

  if autocomplete:
    field.autocomplete_attribute = autocomplete

  field.concepts.append("unset")

  field.section = address_pb2.ExampleSequenceSection.OTHER
  if "CREDIT_CARD_" in overall_type:
    field.section = address_pb2.ExampleSequenceSection.PAYMENT
  elif "ADDRESS_" in overall_type or "COMPANY_NAME" in overall_type:
    field.section = address_pb2.ExampleSequenceSection.ADDRESS
  elif "NAME_" in overall_type:
    field.section = address_pb2.ExampleSequenceSection.NAME
  elif "PHONE" in overall_type:
    field.section = address_pb2.ExampleSequenceSection.PHONE
  elif "EMAIL" in overall_type:
    field.section = address_pb2.ExampleSequenceSection.OTHER


print(text_format.MessageToString(ontology, as_utf8=True))
