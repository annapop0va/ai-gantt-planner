type ClassValue = string | false | null | undefined

/** Minimal class-name joiner — avoids pulling in `clsx` for one function. */
export function cx(...values: ClassValue[]): string {
  return values.filter(Boolean).join(' ')
}
