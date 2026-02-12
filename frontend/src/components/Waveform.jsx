export default function Waveform({ isPlaying }) {
  if (!isPlaying) return null;

  return (
    <div className="flex gap-1 mt-4">
      <div className="w-2 h-8 bg-success animate-pulse"></div>
      <div className="w-2 h-12 bg-success animate-pulse delay-75"></div>
      <div className="w-2 h-10 bg-success animate-pulse delay-150"></div>
      <div className="w-2 h-14 bg-success animate-pulse"></div>
      <div className="w-2 h-8 bg-success animate-pulse delay-75"></div>
    </div>
  );
}
