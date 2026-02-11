from .brain import Brain
from .tts_model import TTS

#abstract class
class Agent():
	def __init__(self):
		self.tts = TTS()
		self.brain = Brain()

	def agent_think(self, prompt:str):
		return self.brain.question_answering(prompt)

	def agent_speak(self, text:str):
		return self.tts.text_to_speech(text)
