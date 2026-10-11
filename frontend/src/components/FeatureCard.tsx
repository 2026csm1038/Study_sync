import type { LucideIcon } from 'lucide-react'

type FeatureCardProps = {
  icon: LucideIcon
  title: string
  description: string
  highlighted?: boolean
}

export function FeatureCard({ icon: Icon, title, description, highlighted }: FeatureCardProps) {
  return (
    <article className={`feature-card ${highlighted ? 'feature-card--highlighted' : ''}`}>
      <div className="feature-icon" aria-hidden="true">
        <Icon size={28} strokeWidth={1.7} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </article>
  )
}
