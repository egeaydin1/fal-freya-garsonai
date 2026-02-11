from services.agent.agent import Agent
from services.parser.parser import parse_sentences
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
import uuid
import asyncio

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Agent instance
agent = Agent()

# Storage for processing results
processing_results = {}


class ChatStartResponse(BaseModel):
	task_id: str
	status: str


class TextInput(BaseModel):
	text: str


def process_chat_text(task_id: str, user_text: str):
	"""Background task to process chat from text"""
	try:
		print(f"[{task_id}] Processing started with text: {user_text}")
		processing_results[task_id] = {
			"status": "processing",
			"ai_response": None,
			"segments": []
		}
		
		# 1. AI - Get response (STT zaten frontend'de yapıldı)
		ai_response = agent.agent_think(user_text)
		print(f"[{task_id}] AI response: {ai_response}")
		processing_results[task_id]["ai_response"] = ai_response
		processing_results[task_id]["status"] = "tts_processing"
		
		# 2. Parse - Split into sentences
		parsed_sentences = parse_sentences(ai_response)
		print(f"[{task_id}] Parsed {len(parsed_sentences)} sentences")
		
		# 3. TTS - Convert each sentence to speech
		for i, sentence in enumerate(parsed_sentences):
			audio_url = agent.agent_speak(sentence)
			segment = {
				"index": i,
				"text": sentence,
				"audio_url": audio_url
			}
			processing_results[task_id]["segments"].append(segment)
			print(f"[{task_id}] Segment {i} ready: {sentence[:30]}...")
		
		processing_results[task_id]["status"] = "completed"
		print(f"[{task_id}] Processing completed")
		
	except Exception as e:
		print(f"[{task_id}] Error: {str(e)}")
		import traceback
		traceback.print_exc()
		processing_results[task_id] = {
			"status": "error",
			"error": str(e)
		}


@router.post("/chat-text", response_model=ChatStartResponse)
async def start_chat_text(text_input: TextInput, background_tasks: BackgroundTasks):
	"""
	Start chat processing from text (STT already done in frontend)
	"""
	task_id = str(uuid.uuid4())
	background_tasks.add_task(process_chat_text, task_id, text_input.text)
	
	return ChatStartResponse(
		task_id=task_id,
		status="started"
	)

@router.get("/stream/{task_id}")
async def stream_chat(task_id: str):
	"""
	Stream audio segments as they become available
	"""
	async def generate():
		try:
			# Wait for task to start
			timeout = 30
			elapsed = 0
			while task_id not in processing_results and elapsed < timeout:
				await asyncio.sleep(0.1)
				elapsed += 0.1
			
			if task_id not in processing_results:
				yield json.dumps({"type": "error", "data": "Task not found"}) + "\n"
				return
			
			# Stream AI response when ready
			while processing_results[task_id]["ai_response"] is None:
				if processing_results[task_id]["status"] == "error":
					yield json.dumps({
						"type": "error",
						"data": processing_results[task_id].get("error", "Unknown error")
					}) + "\n"
					return
				await asyncio.sleep(0.1)
			
			yield json.dumps({
				"type": "ai_response",
				"data": processing_results[task_id]["ai_response"]
			}) + "\n"
			
			# Stream segments as they become ready
			sent_count = 0
			while True:
				current_segments = len(processing_results[task_id]["segments"])
				
				# Send new segments
				while sent_count < current_segments:
					segment = processing_results[task_id]["segments"][sent_count]
					yield json.dumps({
						"type": "audio_segment",
						"data": segment
					}) + "\n"
					sent_count += 1
				
				# Check if completed
				if processing_results[task_id]["status"] == "completed":
					yield json.dumps({"type": "complete"}) + "\n"
					# Cleanup after a delay
					await asyncio.sleep(60)
					if task_id in processing_results:
						del processing_results[task_id]
					break
				
				if processing_results[task_id]["status"] == "error":
					yield json.dumps({
						"type": "error",
						"data": processing_results[task_id].get("error", "Unknown error")
					}) + "\n"
					break
				
				await asyncio.sleep(0.2)
				
		except Exception as e:
			print(f"[Stream {task_id}] Error: {str(e)}")
			yield json.dumps({"type": "error", "data": str(e)}) + "\n"
	
	return StreamingResponse(generate(), media_type="application/x-ndjson")
