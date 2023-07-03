from collections import defaultdict
from typing import Optional
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
import os


class Renderer:
  output_dir: Optional[str] = None

  # Key/value pairs exposed to the renderer.
  data = dict()
  # Key/value paris exposed to the renderer, where the key is a country code.
  country_data = defaultdict(dict)

  countries = []

  def __init__(self, output_dir: Optional[str] = None):
    self.output_dir = output_dir

  def add_country(self, country: str) -> None:
    if country in self.countries:
      return
    self.countries.append(country)
    # Put "global" first.
    self.countries.sort(key=lambda c: "" if c == "global" else c)

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

  def render_country(self, country: str, css: str, content: str,
                     javascript: str) -> None:
    template = self._load_template("base.html")

    result = template.render(country=country,
                             countries=self.countries,
                             data=self.data,
                             country_data=self.country_data,
                             css=css,
                             content=content,
                             javascript=javascript)

    dir = "out"
    if self.output_dir:
      dir = self.output_dir
    f = open(f"{dir}/{country}.html", "w")
    f.write(result)
    f.close()
