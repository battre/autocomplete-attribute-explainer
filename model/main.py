import argparse
from modules.abstract_module import AbstractModule
from modules.metadata import MetadataModule
from modules.model import ParseCountryModelModule, ParseGlobalModelModule, RenderTokenIndexModule, ParseDescriptionsModelModule, RenderTokenChildrenModule
from modules.formatting import FormattingModule
from modules.graphs import GraphsModule
from abstract_vendor_extension import AbstractVendorExtension
from pathlib import Path
from renderer import Renderer

modules: list[AbstractModule] = [
    MetadataModule(),
    ParseGlobalModelModule(),
    ParseCountryModelModule(),
    ParseDescriptionsModelModule(),
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

renderer = Renderer(args.out)

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

  all_token_content = ""
  for token in renderer.country_data[country]["model"].pre_order_only_uniques():
    token_content = ""
    for module in modules:
      if new_token_conent := module.render_token_details(
          country, token.id, renderer):
        token_content += new_token_conent
    token_content = renderer.wrap_token_details(
        token.id, renderer.country_data[country]["model"], token_content)
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
