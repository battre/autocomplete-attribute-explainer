from renderer import Renderer
from modules.abstract_module import AbstractModule
from typing import Optional
import os
from renderer import Renderer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from modules.model.model import AtomicOrCompoundToken


class RenderTokenIndexModule(AbstractModule):

  def css(self) -> Optional[str]:
    return """
    <style>
    .concept {
      border-style: solid;
      border-width: 1px;
      border-color: #EEE;
    }
    .concept-id {
      padding: 4px;
      background-color: #EEE;
    }
    .concept-content {
      padding: 4px 4px 4px 16px ;
    }
    </style>
    """

  def render_token_index(self, country: str,
                         renderer: Renderer) -> Optional[str]:
    env = Environment(
        extensions=['jinja2.ext.do'],
        loader=FileSystemLoader(os.path.join(os.path.dirname(__file__))),
        autoescape=select_autoescape())
    template = env.get_template("token_index_template.html")
    model = renderer.country_data[country]["model"]
    return template.render(
        model=model, country_data=renderer.country_data[country])
