import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { dbOptions } from "./schema";

export function createClient() {
  const cookieStore = cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      ...dbOptions,
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options?: Record<string, unknown> }[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Ignorado quando chamado de Server Component (cookies só podem ser setados em Route Handlers/Server Actions).
            // O middleware cuida do refresh da sessão.
          }
        },
      },
    },
  );
}
