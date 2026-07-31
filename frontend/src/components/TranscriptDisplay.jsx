export default function TranscriptDisplay({ transcript }) {
  if (!transcript) return null;

  return (
    <div className="w-full mt-6 p-4 bg-base-200 rounded-lg">
      <p className="text-sm opacity-70 mb-1">You said:</p>
      <p className="text-lg">{transcript}</p>
    </div>
  );
}
