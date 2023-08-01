from renderer import Renderer
from modules.abstract_module import AbstractModule
from typing import Optional
from renderer import Renderer
from modules.model.model import AtomicOrCompoundToken


class RenderTokenChildrenModule(AbstractModule):

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

  def render_token_details(self, country: str, token_id: str,
                           renderer: Renderer) -> Optional[str]:
    template = RenderTokenChildrenModule.get_template(__file__,
                                                      "token_children.html")
    model = renderer.get_model(country)
    return template.render(token=model.find_token(token_id))
