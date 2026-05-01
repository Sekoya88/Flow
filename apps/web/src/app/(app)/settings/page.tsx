"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Loader2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiFetch } from "@/lib/api";
import { getToken } from "@/lib/auth";

type Prefs = { preferences: { key: string; value: unknown; updated_at: string }[] };

export default function SettingsPage() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [prefs, setPrefs] = useState<Prefs["preferences"]>([]);
  const [key, setKey] = useState("style");
  const [val, setVal] = useState('{"tone":"concise"}');
  const [loadingPrefs, setLoadingPrefs] = useState(true);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    if (!getToken()) {
      routerRef.current.replace("/login");
      return;
    }
    setLoadingPrefs(true);
    setLoadErr(null);
    apiFetch<Prefs>("/api/v1/user/preferences")
      .then((r) => setPrefs(r.preferences))
      .catch((e) => {
        setLoadErr(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
      })
      .finally(() => setLoadingPrefs(false));
  }, []);

  async function save() {
    setSaveErr(null);
    let parsed: unknown = val;
    try {
      parsed = JSON.parse(val);
    } catch {
      parsed = { raw: val };
    }
    setSaving(true);
    try {
      await apiFetch("/api/v1/user/preferences", { method: "PUT", json: { key, value: parsed } });
      const r = await apiFetch<Prefs>("/api/v1/user/preferences");
      setPrefs(r.preferences);
    } catch (e) {
      setSaveErr(e instanceof ApiError ? `${e.status}: ${e.body}` : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground text-sm">User preferences merged into agent runs.</p>
      </div>
      {loadErr ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Could not load preferences</AlertTitle>
          <AlertDescription>{loadErr}</AlertDescription>
        </Alert>
      ) : null}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add preference</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="k">Key</Label>
            <Input id="k" value={key} onChange={(e) => setKey(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="v">Value (JSON)</Label>
            <Textarea id="v" value={val} onChange={(e) => setVal(e.target.value)} rows={4} />
          </div>
          <Button onClick={() => void save()} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              "Save"
            )}
          </Button>
          {saveErr ? (
            <p className="text-destructive text-sm" role="alert">
              {saveErr}
            </p>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Saved</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingPrefs ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Loading…
            </div>
          ) : (
          <ul className="space-y-2 text-sm font-mono">
            {prefs.map((p) => (
              <li key={p.key}>
                <span className="text-primary">{p.key}</span>: {JSON.stringify(p.value)}
              </li>
            ))}
            {prefs.length === 0 ? <li className="text-muted-foreground">None yet.</li> : null}
          </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
