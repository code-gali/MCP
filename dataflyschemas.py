from pydantic import BaseModel
from typing import List,Dict
class PromptContent(BaseModel):
    prompt_name:str
    description:str
    content:str


class PromptModel(BaseModel):
    uri: str
    prompt: PromptContent

class FrequentQuestionModel(BaseModel):
    uri: str
    questions:List[Dict[str,str]]
