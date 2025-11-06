import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ReactMarkdown from "react-markdown";

export default function AnswerTabs({ answers }) {
  const [active, setActive] = useState("0");

  if (!answers || answers.length === 0) return null;

  return (
    <Tabs value={active} onValueChange={setActive} className="w-full mt-4">
      <TabsList>
        {answers.map((_, i) => (
          <TabsTrigger key={i} value={String(i)}>
            {i === 0 ? "Κύρια απάντηση" : `Εναλλακτική ${i}`}
          </TabsTrigger>
        ))}
      </TabsList>

      {answers.map((a, i) => (
        <TabsContent key={i} value={String(i)}>
          <div className="prose prose-lg text-justify">
            <ReactMarkdown>{a}</ReactMarkdown>
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
