"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Send, Bot, User, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { askCopilot, type CopilotResult } from "@/lib/features";
import { cn } from "@/lib/utils";

type Message =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; result: CopilotResult };

const EXAMPLES = [
  "Vì sao doanh số váy hoa nhí giảm?",
  "Đối thủ giảm giá kem chống nắng, tôi nên làm gì?",
  "Nên hợp tác KOL nào cho mỹ phẩm?",
  "Hôm nay tôi nên làm gì?",
];

function vnd(n: number) {
  return n.toLocaleString("vi-VN") + "₫";
}

export function CopilotPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, busy]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(false);
    setDraft("");
    setMessages((prev) => [...prev, { id: `u${Date.now()}`, role: "user", text: q }]);

    const r = await askCopilot(q);
    setError(r === null);
    if (r) {
      setMessages((prev) => [...prev, { id: `a${Date.now()}`, role: "assistant", result: r }]);
    }
    setBusy(false);
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="lg:col-span-8">
        <div className="flex h-[640px] flex-col rounded-[10px] border border-border bg-surface">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="live-dot" />
              <span className="mono text-2xs uppercase tracking-wider text-text-dim">
                copilot · agent ready
              </span>
            </div>
            <Badge variant="live">tool-routing agent</Badge>
          </div>

          <div ref={listRef} className="flex-1 space-y-5 overflow-y-auto px-4 py-5">
            {!hasMessages && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Bot className="h-9 w-9 text-accent" />
                <p className="mt-3 text-sm font-medium text-text">Hỏi bất cứ điều gì về shop của bạn</p>
                <p className="mt-1 max-w-sm text-xs text-text-muted">
                  Agent sẽ tự chọn công cụ phù hợp — phân tích doanh số, giá đối thủ, KOL, tồn kho… — và trả lời kèm tác động doanh thu ước tính.
                </p>
              </div>
            )}

            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex items-start justify-end gap-2.5">
                  <div className="max-w-[80%] rounded-[10px] rounded-tr-sm bg-accent/15 px-3.5 py-2.5 text-sm text-text">
                    {m.text}
                  </div>
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-bg-alt text-text-muted">
                    <User className="h-3.5 w-3.5" />
                  </span>
                </div>
              ) : (
                <div key={m.id} className="flex items-start gap-2.5">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-accent/40 bg-accent/10 text-accent">
                    <Bot className="h-3.5 w-3.5" />
                  </span>
                  <div className="min-w-0 max-w-[85%] space-y-2.5">
                    <div className="rounded-[10px] rounded-tl-sm border border-border bg-bg-alt px-3.5 py-2.5">
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-text">{m.result.answer}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="muted">
                        <Wrench className="h-3 w-3" />
                        {m.result.skill_used}
                      </Badge>
                      {m.result.entity && (
                        <span className="mono text-2xs text-text-dim">{m.result.entity}</span>
                      )}
                      {m.result.impact_vnd != null && (
                        <span className="inline-flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/10 px-2 py-0.5">
                          <span className="mono text-2xs uppercase tracking-wider text-text-dim">Tác động ước tính</span>
                          <span className="mono text-xs font-semibold text-accent">{vnd(m.result.impact_vnd)}</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ),
            )}

            {busy && (
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Agent đang chọn công cụ và phân tích…
              </div>
            )}
            {error && (
              <p className="text-sm text-danger">Không lấy được câu trả lời. Kiểm tra kết nối backend rồi thử lại.</p>
            )}
          </div>

          <div className="border-t border-border p-3">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send(draft);
              }}
              className="flex items-center gap-2"
            >
              <Input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Hỏi copilot — ví dụ: vì sao doanh số giảm tuần này?"
                disabled={busy}
                className="h-10"
              />
              <Button type="submit" size="lg" disabled={busy || !draft.trim()}>
                {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                Gửi
              </Button>
            </form>
          </div>
        </div>
      </div>

      <aside className="lg:col-span-4 space-y-4">
        <div className="rounded-[10px] border border-border bg-surface p-4">
          <div className="mono text-2xs uppercase tracking-wider text-text-dim">Câu hỏi mẫu</div>
          <div className="mt-3 flex flex-col gap-2">
            {EXAMPLES.map((q) => (
              <button
                key={q}
                type="button"
                disabled={busy}
                onClick={() => send(q)}
                className={cn(
                  "rounded-md border border-border bg-bg-alt px-3 py-2 text-left text-xs text-text-muted transition-colors",
                  "hover:border-accent hover:text-text disabled:opacity-50",
                )}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-[10px] border border-border bg-surface p-4 text-xs text-text-muted">
          <span className="mono text-2xs uppercase tracking-wider text-text-dim">Cách hoạt động</span>
          <p className="mt-2">
            Copilot là một agent điều phối: từ câu hỏi tiếng Việt, nó chọn đúng công cụ trong bộ tính năng seller
            (giá, doanh số, KOL, tồn kho…), gọi công cụ đó và tổng hợp câu trả lời kèm{" "}
            <span className="mono text-text">tác động doanh thu</span> ước tính.
          </p>
        </div>
      </aside>
    </div>
  );
}
