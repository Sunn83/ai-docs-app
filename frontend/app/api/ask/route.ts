import { NextResponse } from 'next/server'
import axios from 'axios'

export async function POST(req: Request) {
  const { question } = await req.json()
  const res = await axios.post('http://backend:8000/api/ask', { question })
  return NextResponse.json(res.data)
}
