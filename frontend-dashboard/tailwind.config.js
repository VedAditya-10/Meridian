/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // Canvas (backgrounds)
                'canvas-night': '#1c1c1c',
                'canvas-night-soft': '#202020',

                // Text colors
                'on-dark': '#ffffff',
                'on-primary': '#ffffff',
                'ink-mute-1': '#b3b3b3',
                'ink-mute-2': '#9a9a9a',
                'ink-mute-3': '#7a7a7a',

                // Accent (orange - Cyberpunk theme)
                'accent': '#ea580c',
                'accent-hover': '#f97316',
                'accent-pressed': '#c2410c',

                // Borders
                'line-subtle': '#2a2a2a',
                'line-soft': '#333333',
                'line-medium': '#404040',

                // Semantic colors
                'semantic-success': '#10b981',
                'semantic-warning': '#f59e0b',
                'semantic-danger': '#ef4444',
                'semantic-info': '#3b82f6',
            },
            fontFamily: {
                sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
            },
            fontSize: {
                'display-xl': ['2.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '500' }],
                'display-lg': ['2rem', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '500' }],
                'display-md': ['1.5rem', { lineHeight: '1.3', letterSpacing: '-0.015em', fontWeight: '500' }],
                'display-sm': ['1.25rem', { lineHeight: '1.4', letterSpacing: '-0.01em', fontWeight: '500' }],
                'body-lg': ['1rem', { lineHeight: '1.5', letterSpacing: '0', fontWeight: '400' }],
                'body-md': ['0.875rem', { lineHeight: '1.5', letterSpacing: '0', fontWeight: '400' }],
                'body-sm': ['0.75rem', { lineHeight: '1.5', letterSpacing: '0', fontWeight: '400' }],
            },
            borderRadius: {
                'xs': '4px',
                'sm': '6px',
                'DEFAULT': '8px',
                'md': '8px',
                'lg': '12px',
                'xl': '16px',
            },
            spacing: {
                '0.5': '2px',
                '1': '4px',
                '1.5': '6px',
                '2': '8px',
                '3': '12px',
                '4': '16px',
                '5': '20px',
                '6': '24px',
                '8': '32px',
                '10': '40px',
                '12': '48px',
                '16': '64px',
                '20': '80px',
            },
            boxShadow: {
                'accent-sm': '0 0 0 1px rgba(234, 88, 12, 0.1)',
                'accent-md': '0 0 0 2px rgba(234, 88, 12, 0.2)',
                'accent-glow': '0 0 20px rgba(234, 88, 12, 0.15)',
            },
            backdropBlur: {
                'xs': '4px',
                'sm': '8px',
                'md': '12px',
                'lg': '20px',
            },
        },
    },
    plugins: [],
}
