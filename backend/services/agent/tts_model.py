import fal_client
from dotenv import load_dotenv

load_dotenv()

class TTS:

	def on_queue_update(self, update):
		if isinstance(update, fal_client.InProgress):
			for log in update.logs:
				print(log["message"])

	def text_to_speech(self, text:str): #it returns only link of speech not any of them
		result = fal_client.subscribe(
			"freya-mypsdi253hbk/freya-tts/generate",
			arguments={
				"input": text
			},
			with_logs=True,
			on_queue_update=self.on_queue_update,
		)
		return (result["audio"]["url"])
