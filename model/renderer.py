from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Any, List
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
import os


@dataclass
class ExtraPage:
  # Human readable part of a link that describes the extra page.
  description: str
  # The path suffix (e.g. "-foo" if the generated files are
  # "<country>-foo.html").
  path_suffix: str


class Renderer:
  output_dir: Optional[str] = None

  # Key/value pairs exposed to the renderer.
  data = dict()
  # Key/value paris exposed to the renderer, where the key is a country code.
  country_data = defaultdict(dict)

  countries = []
  vendor_extension_extra_pages: List[ExtraPage] = []
  LEGACY_COUNTRT_CODE = "XX"

  def __init__(self,
               output_dir: Optional[str] = None,
               vendor_extension_extra_pages: List[ExtraPage] = []):
    self.output_dir = output_dir
    self.vendor_extension_extra_pages = vendor_extension_extra_pages

  def add_country(self, country: str) -> None:
    if country in self.countries:
      return
    self.countries.append(country)
    # Put "global" first.
    self.countries.sort(key=lambda c: "" if c == "global" else c)

  def get_model(self, country: str) -> Optional[Any]:
    return self.country_data[country].get("model")

  def set_model(self, country: str, model: Any):
    self.country_data[country]["model"] = model

  def _load_template(self, filename) -> Template:
    env = Environment(extensions=['jinja2.ext.do'],
                      loader=FileSystemLoader(
                          os.path.join(os.path.dirname(__file__), "template")),
                      autoescape=select_autoescape())
    return env.get_template(filename)

  def wrap_token_details(self, id, model, content) -> str:
    template = self._load_template("details_token_wrapper.html")
    return template.render(id=id, model=model, content=content)

  def wrap_all_token_details(self, content) -> str:
    template = self._load_template("details_global_wrapper.html")
    return template.render(content=content)

  def render_country(self,
                     country: str,
                     css: str,
                     content: str,
                     javascript: str,
                     file_suffix="") -> None:
    template = self._load_template("base.html")

    result = template.render(
        country=country,
        countries=self.countries,
        data=self.data,
        country_data=self.country_data,
        css=css,
        content=content,
        javascript=javascript,
        file_suffix=file_suffix,
        vendor_extension_extra_pages=self.vendor_extension_extra_pages)

    dir = "out"
    if self.output_dir:
      dir = self.output_dir
    f = open(f"{dir}/{country}{file_suffix}.html", "w")
    f.write(result)
    f.close()
