from modules.metadata import MetadataModule
from modules.model import ParseCountryModelModule, ParseGlobalModelModule, RenderTokenIndexModule, ParseDescriptionsModelModule, RenderTokenChildrenModule
from pathlib import Path
from renderer import Renderer

modules = [
    MetadataModule(),
    ParseGlobalModelModule(),
    ParseCountryModelModule(),
    ParseDescriptionsModelModule(),
    RenderTokenIndexModule(),
    RenderTokenChildrenModule(),
]
global_config_files = list(Path('.').glob('countries/*/global-*.yaml'))
other_config_files = list(Path('.').glob('countries/*/??-*.yaml'))
renderer = Renderer()

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