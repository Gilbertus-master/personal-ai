'use client';

import { useCallback, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { Check, Copy } from 'lucide-react';
import type { Components } from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded bg-[var(--surface-hover)] text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
      aria-label="Kopiuj kod"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

const components: Components = {
  pre({ children, ...props }) {
    // Extract code text for copy button
    let codeText = '';
    if (
      children &&
      typeof children === 'object' &&
      'props' in (children as React.ReactElement)
    ) {
      const child = children as React.ReactElement<{ children?: string }>;
      codeText = typeof child.props.children === 'string' ? child.props.children : '';
    }

    return (
      <div className="relative group my-3">
        <pre
          className="bg-[var(--surface)] rounded-lg p-4 overflow-x-auto text-sm font-mono border border-[var(--border)]"
          {...props}
        >
          {children}
        </pre>
        <div className="opacity-0 group-hover:opacity-100 transition-opacity">
          <CopyButton text={codeText} />
        </div>
      </div>
    );
  },
  code({ className, children, ...props }) {
    const isInline = !className;
    if (isInline) {
      return (
        <code
          className="bg-[var(--surface)] px-1.5 py-0.5 rounded text-sm font-mono border border-[var(--border)]"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={`${className ?? ''} font-mono`} {...props}>
        {children}
      </code>
    );
  },
  a({ href, children, ...props }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[var(--accent)] hover:underline"
        {...props}
      >
        {children}
      </a>
    );
  },
  table({ children, ...props }) {
    return (
      <div className="overflow-x-auto my-3">
        <table
          className="w-full border-collapse border border-[var(--border)] text-sm"
          {...props}
        >
          {children}
        </table>
      </div>
    );
  },
  thead({ children, ...props }) {
    return (
      <thead className="bg-[var(--surface)]" {...props}>
        {children}
      </thead>
    );
  },
  th({ children, ...props }) {
    return (
      <th
        className="border border-[var(--border)] px-3 py-2 text-left font-semibold"
        {...props}
      >
        {children}
      </th>
    );
  },
  td({ children, ...props }) {
    return (
      <td className="border border-[var(--border)] px-3 py-2" {...props}>
        {children}
      </td>
    );
  },
  p({ children, ...props }) {
    return (
      <p className="my-2 leading-relaxed" {...props}>
        {children}
      </p>
    );
  },
  h1({ children, ...props }) {
    return (
      <h1 className="text-2xl font-bold mt-6 mb-3" {...props}>
        {children}
      </h1>
    );
  },
  h2({ children, ...props }) {
    return (
      <h2 className="text-xl font-bold mt-5 mb-2" {...props}>
        {children}
      </h2>
    );
  },
  h3({ children, ...props }) {
    return (
      <h3 className="text-lg font-semibold mt-4 mb-2" {...props}>
        {children}
      </h3>
    );
  },
  h4({ children, ...props }) {
    return (
      <h4 className="text-base font-semibold mt-3 mb-1" {...props}>
        {children}
      </h4>
    );
  },
  h5({ children, ...props }) {
    return (
      <h5 className="text-sm font-semibold mt-3 mb-1" {...props}>
        {children}
      </h5>
    );
  },
  h6({ children, ...props }) {
    return (
      <h6 className="text-sm font-medium mt-2 mb-1" {...props}>
        {children}
      </h6>
    );
  },
  ul({ children, ...props }) {
    return (
      <ul className="list-disc list-inside my-2 space-y-1" {...props}>
        {children}
      </ul>
    );
  },
  ol({ children, ...props }) {
    return (
      <ol className="list-decimal list-inside my-2 space-y-1" {...props}>
        {children}
      </ol>
    );
  },
  li({ children, ...props }) {
    return (
      <li className="leading-relaxed" {...props}>
        {children}
      </li>
    );
  },
  blockquote({ children, ...props }) {
    return (
      <blockquote
        className="border-l-4 border-[var(--accent)] bg-[var(--surface-hover)] pl-4 py-2 my-3 italic"
        {...props}
      >
        {children}
      </blockquote>
    );
  },
  hr({ ...props }) {
    return <hr className="border-[var(--border)] my-4" {...props} />;
  },
};

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="text-[var(--text)] prose-invert max-w-none">
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {content}
      </Markdown>
    </div>
  );
}
