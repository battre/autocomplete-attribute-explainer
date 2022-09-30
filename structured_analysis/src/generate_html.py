# This tool takes a couple of .textproto files containig a AddressOntology
# proto and assembles a human readable representation via "template.html"
# into the file "out.html"

import address_pb2
import argparse
from typing import Generator
from google.protobuf import text_format
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import sys

parser = argparse.ArgumentParser(
    description="Generates the summary of information from the provided "
    "textprotos.")
parser.add_argument(
    "--output",
    type=str,
    metavar="output",
    help="HTML file to generate",
    required=True,
)
parser.add_argument(
    'input',
    metavar='inputs',
    type=str,
    nargs='+',
    help='Textproto files containing a AddressOntology object')

args = parser.parse_args()

# Uses the address_pb2.ExampleFieldSequence.fields.section attribute to
# gather all fields with a common value in one address_pb2.ExampleFieldSequence.
def split_sequence(sequence: address_pb2.ExampleFieldSequence
                  ) -> Generator[address_pb2.ExampleFieldSequence, None, None]:
  # Build a list of the different unique values of
  # address_pb2.ExampleFieldSequence.fields.section
  # sorted by order of occurrence.
  sections_found = []
  for field in sequence.fields:
    if field.section not in sections_found:
      sections_found.append(field.section)

  # Create a new address_pb2.ExampleFieldSequence for each value of the section.
  for section in sections_found:
    new_sequence = address_pb2.ExampleFieldSequence()
    new_sequence.section = section
    for field in sequence.fields:
      if field.section == section:
        new_sequence.fields.append(field)
    yield new_sequence


# Takes each address_pb2.ExampleFieldSequence of site_example and splits it
# into multiple ExampleFieldSequences of fields which share a common section.
def split_sequences(site_example: address_pb2.SiteExample) -> None:
  old_site_example = address_pb2.SiteExample()
  old_site_example.CopyFrom(site_example)
  del site_example.sequences[:]
  for sequence in old_site_example.sequences:
    for new_sequence in split_sequence(sequence):
      site_example.sequences.append(new_sequence)


# Populates an "internal_id" with values that are unique for each field.
# This allows us to reference the values in the HTML code.
def assign_ids_to_fields(ontology: address_pb2.AddressOntology) -> None:
  counter = 0
  for site in ontology.site_examples:
    for sequence in site.sequences:
      for field in sequence.fields:
        field.internal_id = "field_{}".format(counter)
        counter = counter + 1


def remove_if_hidden(container) -> None:
  items_to_remove = [item for item in container if item.hide]
  for item in items_to_remove:
    container.remove(item)


# The main program.

if len(sys.argv) == 1:
  print("Usage:", sys.argv[0], "files.textproto")
  sys.exit(-1)

# Merge all ontology files into one big data structure.
ontology = address_pb2.AddressOntology()
for file in args.input: # sys.argv[1:]:
  # Read and parse ontology file.
  f = open(file, "rb")
  ontology_in_file = address_pb2.AddressOntology()
  text_format.Parse(f.read(), ontology_in_file)
  f.close()
  ontology.MergeFrom(ontology_in_file)

# Remove everything that is hidden.
remove_if_hidden(ontology.site_examples)
for site_example in ontology.site_examples:
  remove_if_hidden(site_example.sequences)
  for sequence in site_example.sequences:
    remove_if_hidden(sequence.fields)

# Split sequences of fields by type [address, phone, address] becomes
# [address, address], [phone].
for site_example in ontology.site_examples:
  split_sequences(site_example)

# Give every field a unique id.
assign_ids_to_fields(ontology)

# Determine all known concepts (e.g. first name, address-level1, ...) in the
# ontology.
known_concepts = set()
new_concepts = set()
for concept in ontology.concepts:
  known_concepts.add(concept.name)
  if concept.is_new:
    new_concepts.add(concept.name)
for concept in ontology.compound_concepts:
  known_concepts.add(concept.name)
  new_concepts.add(concept.name)

# Determine all countries for which we have examples.
countries = set([example.locale.country for example in ontology.site_examples])

# Render everything to out.html.
env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape())
template = env.get_template("template.html")
result = template.render(
    ontology=ontology,
    countries=countries,
    address_pb2=address_pb2,
    rtl_languages=set(["ar"]),
    known_concepts=known_concepts,
    new_concepts=new_concepts)
f = open(args.output, "w")
f.write(result)
f.close()
