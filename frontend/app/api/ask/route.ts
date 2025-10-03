import { NextResponse } from "next/server";
import axios from "axios";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q");

  const res = await axios.get("http://backend:8000/ask", { params: { q } });
  return NextResponse.json(res.data);
}
