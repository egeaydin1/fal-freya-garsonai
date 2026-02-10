import fal_client
from dotenv import load_dotenv

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

