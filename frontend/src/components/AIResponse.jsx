export default function AIResponse({ response }) {
  if (!response) return null;

  return (
    <div className="w-full mt-4 p-4 bg-primary/10 rounded-lg">
      <p className="text-sm opacity-70 mb-1">GarsonAI:</p>
      <p className="text-lg">{response}</p>
    </div>
  );
}
