import React, { useState } from "react";
import axios from "axios";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post("/api/ask", { question });
      setAnswer(res.data.answer);
    } catch (err) {
      console.error(err);
      setAnswer("Σφάλμα server");
    }
  };

  return (
    <div>
      <h1>AI Docs App</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Γράψε την ερώτηση σου"
        />
        <button type="submit">Ρώτα</button>
      </form>
      <p>{answer}</p>
    </div>
  );
}

export default App;
