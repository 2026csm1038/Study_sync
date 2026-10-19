import { CircleCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

const POINTS = ['Previous year papers', 'Assignments', 'Quizzes', 'Course-wise resources']


export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth-page">
      <section className="auth-left">
        <Link to="/" className="auth-brand" aria-label="StudySync home">
          <img src="/assets/logo-mark.png" alt=""  />
          <span>
            Study<em>Sync</em>
          </span>
        </Link>

        <h1>
          Your academic resources,
          <br />
          all in one place.
        </h1>
        <p className="auth-lead">
          Find previous-year papers, assignments and quizzes for your courses.
        </p>

        <ul className="auth-points">
          {POINTS.map((point) => (
            <li key={point}>
              <CircleCheck size={30} strokeWidth={1.6} aria-hidden="true" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="auth-right">
        <div className="auth-card">{children}</div>
      </section>
    </div>
  )
}
