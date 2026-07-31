export default function StatusBadge({ status }) {
  return (
    <div className="badge badge-lg mb-4">
      {status === "idle" && "Ready"}
      {status === "connected" && "Connected"}
      {status === "listening" && "Listening..."}
      {status === "processing" && "Processing..."}
      {status === "disconnected" && "Disconnected"}
      {status.startsWith("Error") && status}
    </div>
  );
}
