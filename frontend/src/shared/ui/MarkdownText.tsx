import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ComponentProps } from 'react'

type Props = {
  text: string
  className?: string
}

export default function MarkdownText({ text, className }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className={className}
      components={{
        p: ({ children }) => <p className="mb-1.5 leading-[1.5] last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-2 list-outside list-disc space-y-0.5 pl-4">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 list-outside list-decimal space-y-0.5 pl-4">{children}</ol>,
        li: ({ children }) => <li className="leading-[1.5] marker:text-slate-400">{children}</li>,
        strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        a: ({ children, href, ...rest }: ComponentProps<'a'>) => (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 underline underline-offset-2"
            {...rest}
          >
            {children}
          </a>
        ),
        pre: ({ children }) => (
          <pre className="my-2 overflow-x-auto rounded-xl bg-slate-900/95 p-3 text-[0.85em] text-slate-50">
            {children}
          </pre>
        ),
        code: ({ children, className, ...rest }) => {
          const isBlock = typeof className === 'string' && className.includes('language-')
          if (isBlock) {
            return (
              <code className={className} {...rest}>
                {children}
              </code>
            )
          }
          return (
            <code
              className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-800"
              {...rest}
            >
              {children}
            </code>
          )
        },
      }}
    >
      {text}
    </ReactMarkdown>
  )
}
