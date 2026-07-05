export function formatPackName(name) {
  return name
    .replace(/^Minifantasy_/, '')
    .replace(/_v\.?\d+\.?\d*(_Commercial_Version)?$/, '')
    .replace(/_/g, ' ')
}
