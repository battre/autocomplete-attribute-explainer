import argparse
from modules.abstract_module import AbstractModule
from modules.comparison_stopwords import ComparisonStopwordsModule
from modules.metadata import MetadataModule
from modules.model import ParseCountryModelModule, ParseGlobalModelModule, RenderTokenIndexModule, ParseDescriptionsModelModule, RenderTokenChildrenModule
from modules.parsing import ParsingModule
from modules.formatting import FormattingModule
from modules.graphs import GraphsModule
from abstract_vendor_extension import AbstractVendorExtension
from pathlib import Path
from renderer import Renderer, ExtraPage
from typing import List


# Function to parse a `--countries=country_list` argument, where the
# country_list looks e.g. like "IN,US".
def list_of_strings(arg: str) -> List[str]:
  return arg.split(',')


# Takes a other_config_file path, which by definition matches
# countries/*/??-*.yaml, and returns the country, which is the first '*' in the
# regex.
def country_of_path(path: Path) -> str:
  return path.parent.name


modules: list[AbstractModule] = [
    MetadataModule(),
    ParseGlobalModelModule(),
    ParseCountryModelModule(),
    ParseDescriptionsModelModule(),
    ParsingModule(),
    ComparisonStopwordsModule(),
    RenderTokenIndexModule(),
    RenderTokenChildrenModule(),
    FormattingModule(),
    GraphsModule(),
]
global_config_files = list(Path('.').glob('countries/*/global-*.yaml'))
other_config_files = list(Path('.').glob('countries/*/??-*.yaml'))

parser = argparse.ArgumentParser()
parser.add_argument('--use_vendor_extension',
                    required=False,
                    action='store_true',
                    help='run vendor extension modules')
parser.add_argument('--out', required=False, help='output directory')
parser.add_argument('--contries', required=False, type=list_of_strings)
args = parser.parse_args()

# If you would like to inject further modules that are vendor specific like
# code generators you can symlink a directory "vendor" that contains a file
# vendor_extension.py with a class VendorExtension that is derived from
# AbstractVendorExtension. This can register new modules and even new config
# files.
if args.use_vendor_extension:
  try:
    from vendor.vendor_extension import VendorExtension
    extension: AbstractVendorExtension = VendorExtension()
    modules = extension.modify_modules_list(modules)
    global_config_files = extension.modify_global_files_list(
        global_config_files)
    other_config_files = extension.modify_other_files_list(other_config_files)
  except ModuleNotFoundError:
    pass
  except ImportError as e:
    raise e

# If an argument like --countries=IN,US was passed, only process the listed
# countries. This is helpful during development to speed up the processing.
if args.contries:
  other_config_files = list(
      filter(lambda path: country_of_path(path) in args.contries,
             other_config_files))

vendor_extension_extra_pages: List[ExtraPage] = []
for module in modules:
  vendor_extension_extra_pages = (vendor_extension_extra_pages +
                                  module.get_extra_pages())

renderer = Renderer(args.out, vendor_extension_extra_pages)

# Read files for the global file (make sure this is fully set up before
# proceeding to the files for other countries).
for module in modules:
  for config_file in global_config_files:
    module.observe_file(config_file, renderer)
# Read files for other countries.
for module in modules:
  for config_file in other_config_files:
    module.observe_file(config_file, renderer)

countries = renderer.countries

# Write results
css = ""
for module in modules:
  if new_css := module.css():
    css += new_css

javascript = ""
for module in modules:
  if new_javascript := module.javascript():
    javascript += new_javascript

for country in countries:
  content = ""

  preamble = ""
  for module in modules:
    if new_preamble := module.render_preamble(country, renderer):
      preamble += new_preamble
  content += preamble

  # Build index for tokens.
  for module in modules:
    field_index = ""
    if new_field_index := module.render_token_index(country, renderer):
      field_index += new_field_index
    content += field_index

  after_token_index = ""
  for module in modules:
    if new_after_token_index := module.render_after_token_index(
        country, renderer):
      after_token_index += new_after_token_index
  content += after_token_index

  all_token_content = ""
  for token in renderer.get_model(country).pre_order_only_uniques():
    token_content = ""
    for module in modules:
      if new_token_conent := module.render_token_details(
          country, token.id, renderer):
        token_content += new_token_conent
    token_content = renderer.wrap_token_details(token.id,
                                                renderer.get_model(country),
                                                token_content)
    all_token_content += token_content
  if all_token_content:
    all_token_content = renderer.wrap_all_token_details(all_token_content)
    content += all_token_content

  epilogue = ""
  for module in modules:
    if new_epilogue := module.render_epilogue(country, renderer):
      epilogue += new_epilogue
  content += epilogue

  renderer.render_country(country, css, content, javascript)

for module in modules:
  module.post_processing(renderer)
