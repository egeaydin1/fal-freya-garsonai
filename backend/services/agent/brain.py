import fal_client
from dotenv import load_dotenv

load_dotenv()

class Brain:

	def on_queue_update(self, update):
		if isinstance(update, fal_client.InProgress):
			for log in update.logs:
				print(log["message"])

	def question_answering(self, prompt:str): #returns only output parameter not all of them
		result = fal_client.subscribe(
			"openrouter/router",
			arguments={
				"model": "openai/gpt-4.1",
				"prompt": prompt,
				"system_prompt": (
					"You are GarsonAI, a professional voice-based restaurant assistant.\n"
					"Rules:\n"
					"- NEVER use emojis.\n"
					"- NEVER use emoticons.\n"
					"- Respond in short, clear Turkish sentences.\n"
					"- Sound polite and natural, like a waiter.\n"
					"""
						- Use one of that words for first word and use '!' after that words:
						Hoş geldiniz,
						Peki,
						Anladım,
						Tabii ki,
						Bir dakika lütfen.
						Make logical decision to use them.
					"""
				),
				"temperature": 0.4
			},
			with_logs=True,
			on_queue_update=self.on_queue_update,
		)
		return(result["output"])
