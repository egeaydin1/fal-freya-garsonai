import fal_client
from dotenv import load_dotenv
from .brain import Brain
from .tts_model import TTS

class STT:

	def on_queue_update(self, update):
		if isinstance(update, fal_client.InProgress):
			for log in update.logs:
				print(log["message"])

	def speech_to_text(self, audio_path: str):
		# Upload local file to FAL
		audio_url = fal_client.upload_file(audio_path)
		
		result = fal_client.subscribe(
			"freya-mypsdi253hbk/freya-stt/generate",
			arguments={
				"audio_url": audio_url
			},
			with_logs=True,
			on_queue_update=self.on_queue_update,
		)
		return result
