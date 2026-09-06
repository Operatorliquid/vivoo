/** Normalize WhatsApp numbers, defaulting numbers without a country prefix to Argentina. */
export function normalizeWhatsAppPhone(value: string): string {
  const trimmed = value.trim();
  let digits = trimmed.replace(/\D/g, '');
  if (!digits) return '';

  const explicitInternational = trimmed.startsWith('+') || digits.startsWith('00');
  if (digits.startsWith('00')) digits = digits.slice(2);

  if (explicitInternational || digits.startsWith('54')) {
    if (digits.startsWith('54') && !digits.startsWith('549')) digits = `549${digits.slice(2).replace(/^0+/, '')}`;
    return `+${digits}`;
  }

  let local = digits.replace(/^0+/, '');
  if (local.length === 12) {
    const mobilePrefixAt = [2, 3, 4].find((index) => local.slice(index, index + 2) === '15');
    if (mobilePrefixAt !== undefined) local = `${local.slice(0, mobilePrefixAt)}${local.slice(mobilePrefixAt + 2)}`;
  }
  return `+549${local}`;
}
