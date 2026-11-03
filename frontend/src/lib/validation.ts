// Entry numbers look like 2026CSM1038 or 2026AIM1022: year + department letters + number.
// Change this pattern if your college uses a different format.
export const ENTRY_NUMBER_RE = /^\d{4}[A-Za-z]{2,5}\d{3,5}$/

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim())
}

export function isValidEntryNumber(value: string): boolean {
  return ENTRY_NUMBER_RE.test(value.trim())
}

/**
 * A professor's email must not look like a student's: student emails are made from the entry number
 * (2026csm1038@iitrpr.ac.in). The server checks this too; this is just the quick message.
 */
export function looksLikeStudentEmail(value: string): boolean {
  return ENTRY_NUMBER_RE.test(value.trim().split('@')[0])
}

/** Returns an error message, or '' when the password is acceptable. */
export function validatePassword(value: string): string {
  if (value.length < 8) return 'Password must be at least 8 characters.'
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    return 'Password must contain at least one letter and one number.'
  }
  return ''
}
