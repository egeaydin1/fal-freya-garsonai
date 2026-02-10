from brain import Brain
from stt_model import STT
from tts_model import TTS

#abstract class
class Agent():
	def __init__(self):
		self.tts = TTS()
		self.stt = STT()
		self.brain = Brain()

	def agent_listen(self, url:str):
		return self.stt.speech_to_text(url)

	def agent_think(self, prompt:str):
		return self.brain.question_answering(prompt)

	def agent_speak(self, text:str):
		return self.tts.text_to_speech(text)
