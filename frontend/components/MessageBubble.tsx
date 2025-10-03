interface Props {
  text: string;
  sender: string;
  sources?: string[];
}

export default function MessageBubble({ text, sender, sources }: Props) {
  return (
    <div className={`mb-3 ${sender === "user" ? "text-right" : "text-left"}`}>
      <div
        className={`inline-block p-3 rounded-lg ${
          sender === "user" ? "bg-blue-500 text-white" : "bg-gray-200"
        }`}
      >
        <p>{text}</p>
        {sources && sources.length > 0 && (
          <p className="text-xs mt-2 text-gray-600">
            📂 Πηγές: {sources.join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}
