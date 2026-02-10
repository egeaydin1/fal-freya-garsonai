import fal_client
from dotenv import load_dotenv
from brain import Brain
from tts_model import TTS

class STT:

	def on_queue_update(self, update):
		if isinstance(update, fal_client.InProgress):
			for log in update.logs:
				print(log["message"])

	def speech_to_text(self, url:str):
		result = fal_client.subscribe(
			"freya-mypsdi253hbk/freya-stt/generate",
			arguments={
				"audio_url": url
			},
			with_logs=True,
			on_queue_update=self.on_queue_update,
		)
		return (result)

ag = Brain()
tts = TTS()
stt = STT()

text = ag.question_answering("selamlar bana ne önerirsiniz?")
print("Before:", text)
speech = tts.text_to_speech(text)
text_after_stt = stt.speech_to_text(speech)
print("After:", text)