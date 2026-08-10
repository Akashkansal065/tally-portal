"use client"

import * as React from "react"

interface InfoTipProps {
  text: string;
}

export function InfoTip({ text }: InfoTipProps) {
  const [show, setShow] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)

  return (
    <div className="relative inline-flex items-center ml-1" ref={ref}>
      <button
        type="button"
        className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-gray-200 hover:bg-gray-300 text-gray-600 hover:text-gray-800 transition-colors text-[10px] font-bold leading-none shrink-0"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onClick={(e) => { e.preventDefault(); setShow(!show); }}
        tabIndex={-1}
      >
        i
      </button>
      {show && (
        <div className="absolute z-[100] bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 px-3 py-2 text-xs text-white bg-gray-900 rounded-lg shadow-lg pointer-events-none">
          <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-gray-900" />
          {text}
        </div>
      )}
    </div>
  )
}
