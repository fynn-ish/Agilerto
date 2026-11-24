// Links to outside sites open in a new tab. They need internet, so the label says so when it matters.
export default function ExternalLink({ href, children, className = '' }) {
  if (!href) return null
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
       className={`text-brand underline underline-offset-2 ${className}`}>
      {children}
    </a>
  )
}
