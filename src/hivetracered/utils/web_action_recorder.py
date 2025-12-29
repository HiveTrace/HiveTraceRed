"""
Web Action Recorder - Browser interaction tracking utility.

This module provides functionality to track and log user interactions in a web browser,
including clicks, text inputs, and text selections. It uses Playwright to inject
JavaScript tracking scripts and capture events.

The recorder can be used both programmatically and as a standalone CLI tool.
"""

import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import sync_playwright, Page, Browser


# JavaScript tracking scripts
CLICK_TRACKER_SCRIPT = """
// Generate CSS selector for an element
function generateCSSSelector(element) {
    if (element.id) {
        return '#' + element.id;
    }

    const path = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
        let selector = current.tagName.toLowerCase();

        if (current.id) {
            selector += '#' + current.id;
            path.unshift(selector);
            break;
        } else {
            let sibling = current;
            let nth = 1;
            while (sibling.previousElementSibling) {
                sibling = sibling.previousElementSibling;
                if (sibling.tagName === current.tagName) {
                    nth++;
                }
            }
            if (nth > 1 || current.nextElementSibling) {
                selector += ':nth-of-type(' + nth + ')';
            }
        }

        path.unshift(selector);
        current = current.parentElement;

        // Limit depth to avoid overly long selectors
        if (path.length >= 5) break;
    }

    return path.join(' > ');
}

// Generate XPath for an element
function generateXPath(element) {
    if (element.id) {
        return '//*[@id="' + element.id + '"]';
    }

    const path = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
        let index = 0;
        let sibling = current.previousSibling;

        while (sibling) {
            if (sibling.nodeType === Node.ELEMENT_NODE && sibling.tagName === current.tagName) {
                index++;
            }
            sibling = sibling.previousSibling;
        }

        const tagName = current.tagName.toLowerCase();
        const pathIndex = index > 0 ? '[' + (index + 1) + ']' : '';
        path.unshift(tagName + pathIndex);

        current = current.parentElement;

        // Limit depth
        if (path.length >= 5) break;
    }

    return '/' + path.join('/');
}

// Get all data-* attributes
function getDataAttributes(element) {
    const dataAttrs = {};
    if (element.attributes) {
        for (let attr of element.attributes) {
            if (attr.name.startsWith('data-')) {
                dataAttrs[attr.name] = attr.value;
            }
        }
    }
    return Object.keys(dataAttrs).length > 0 ? dataAttrs : null;
}

// Get ARIA attributes
function getAriaAttributes(element) {
    const ariaAttrs = {};
    if (element.attributes) {
        for (let attr of element.attributes) {
            if (attr.name.startsWith('aria-')) {
                ariaAttrs[attr.name] = attr.value;
            }
        }
    }
    // Also check role attribute
    if (element.role) {
        ariaAttrs['role'] = element.role;
    }
    return Object.keys(ariaAttrs).length > 0 ? ariaAttrs : null;
}

document.addEventListener('click', (event) => {
    const clickData = {
        x: event.clientX,
        y: event.clientY,
        pageX: event.pageX,
        pageY: event.pageY,
        target: {
            tagName: event.target.tagName,
            id: event.target.id,
            className: event.target.className,
            textContent: event.target.textContent?.substring(0, 100),
            href: event.target.href || null,
            src: event.target.src || null,
            dataAttributes: getDataAttributes(event.target),
            ariaAttributes: getAriaAttributes(event.target)
        },
        // Selectors for reliably finding this element later
        selectors: {
            css: generateCSSSelector(event.target),
            xpath: generateXPath(event.target)
        },
        url: window.location.href,
        button: event.button
    };
    console.log('CLICK_EVENT:', JSON.stringify(clickData));
}, true);
"""

INPUT_TRACKER_SCRIPT = """
// Generate CSS selector for an element
function generateCSSSelector(element) {
    if (element.id) {
        return '#' + element.id;
    }

    const path = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
        let selector = current.tagName.toLowerCase();

        if (current.id) {
            selector += '#' + current.id;
            path.unshift(selector);
            break;
        } else {
            let sibling = current;
            let nth = 1;
            while (sibling.previousElementSibling) {
                sibling = sibling.previousElementSibling;
                if (sibling.tagName === current.tagName) {
                    nth++;
                }
            }
            if (nth > 1 || current.nextElementSibling) {
                selector += ':nth-of-type(' + nth + ')';
            }
        }

        path.unshift(selector);
        current = current.parentElement;

        // Limit depth to avoid overly long selectors
        if (path.length >= 5) break;
    }

    return path.join(' > ');
}

// Generate XPath for an element
function generateXPath(element) {
    if (element.id) {
        return '//*[@id="' + element.id + '"]';
    }

    const path = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
        let index = 0;
        let sibling = current.previousSibling;

        while (sibling) {
            if (sibling.nodeType === Node.ELEMENT_NODE && sibling.tagName === current.tagName) {
                index++;
            }
            sibling = sibling.previousSibling;
        }

        const tagName = current.tagName.toLowerCase();
        const pathIndex = index > 0 ? '[' + (index + 1) + ']' : '';
        path.unshift(tagName + pathIndex);

        current = current.parentElement;

        // Limit depth
        if (path.length >= 5) break;
    }

    return '/' + path.join('/');
}

// Get all data-* attributes
function getDataAttributes(element) {
    const dataAttrs = {};
    if (element.attributes) {
        for (let attr of element.attributes) {
            if (attr.name.startsWith('data-')) {
                dataAttrs[attr.name] = attr.value;
            }
        }
    }
    return Object.keys(dataAttrs).length > 0 ? dataAttrs : null;
}

// Get ARIA attributes
function getAriaAttributes(element) {
    const ariaAttrs = {};
    if (element.attributes) {
        for (let attr of element.attributes) {
            if (attr.name.startsWith('aria-')) {
                ariaAttrs[attr.name] = attr.value;
            }
        }
    }
    // Also check role attribute
    if (element.role) {
        ariaAttrs['role'] = element.role;
    }
    return Object.keys(ariaAttrs).length > 0 ? ariaAttrs : null;
}

// Track keyboard input in text fields
document.addEventListener('input', (event) => {
    const target = event.target;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        const inputData = {
            value: target.value || target.textContent || '',
            target: {
                tagName: target.tagName,
                id: target.id,
                name: target.name || null,
                className: target.className,
                type: target.type || null,
                placeholder: target.placeholder || null,
                dataAttributes: getDataAttributes(target),
                ariaAttributes: getAriaAttributes(target)
            },
            // Selectors for reliably finding this element later
            selectors: {
                css: generateCSSSelector(target),
                xpath: generateXPath(target)
            },
            url: window.location.href
        };
        console.log('INPUT_EVENT:', JSON.stringify(inputData));
    }
}, true);
"""

SELECTION_TRACKER_SCRIPT = """
// Generate CSS selector for an element
function generateCSSSelector(element) {
    if (element.id) {
        return '#' + element.id;
    }

    const path = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
        let selector = current.tagName.toLowerCase();

        if (current.id) {
            selector += '#' + current.id;
            path.unshift(selector);
            break;
        } else {
            let sibling = current;
            let nth = 1;
            while (sibling.previousElementSibling) {
                sibling = sibling.previousElementSibling;
                if (sibling.tagName === current.tagName) {
                    nth++;
                }
            }
            if (nth > 1 || current.nextElementSibling) {
                selector += ':nth-of-type(' + nth + ')';
            }
        }

        path.unshift(selector);
        current = current.parentElement;

        // Limit depth to avoid overly long selectors
        if (path.length >= 5) break;
    }

    return path.join(' > ');
}

// Generate XPath for an element
function generateXPath(element) {
    if (element.id) {
        return '//*[@id="' + element.id + '"]';
    }

    const path = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE) {
        let index = 0;
        let sibling = current.previousSibling;

        while (sibling) {
            if (sibling.nodeType === Node.ELEMENT_NODE && sibling.tagName === current.tagName) {
                index++;
            }
            sibling = sibling.previousSibling;
        }

        const tagName = current.tagName.toLowerCase();
        const pathIndex = index > 0 ? '[' + (index + 1) + ']' : '';
        path.unshift(tagName + pathIndex);

        current = current.parentElement;

        // Limit depth
        if (path.length >= 5) break;
    }

    return '/' + path.join('/');
}

// Get all data-* attributes
function getDataAttributes(element) {
    const dataAttrs = {};
    if (element.attributes) {
        for (let attr of element.attributes) {
            if (attr.name.startsWith('data-')) {
                dataAttrs[attr.name] = attr.value;
            }
        }
    }
    return Object.keys(dataAttrs).length > 0 ? dataAttrs : null;
}

// Get ARIA attributes
function getAriaAttributes(element) {
    const ariaAttrs = {};
    if (element.attributes) {
        for (let attr of element.attributes) {
            if (attr.name.startsWith('aria-')) {
                ariaAttrs[attr.name] = attr.value;
            }
        }
    }
    // Also check role attribute
    if (element.role) {
        ariaAttrs['role'] = element.role;
    }
    return Object.keys(ariaAttrs).length > 0 ? ariaAttrs : null;
}

// Track text selection with debouncing
let selectionTimeout;
document.addEventListener('selectionchange', () => {
    clearTimeout(selectionTimeout);
    selectionTimeout = setTimeout(() => {
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        // Only log if there's actual text selected
        if (selectedText.length > 0) {
            const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

            if (range) {
                // Get the element containing the selection
                const container = range.commonAncestorContainer;
                const element = container.nodeType === 3 ? container.parentElement : container;

                // Get parent elements for context (up to 3 levels)
                const parentChain = [];
                let parent = element;
                for (let i = 0; i < 3 && parent; i++) {
                    parentChain.push({
                        tagName: parent.tagName,
                        id: parent.id || null,
                        className: parent.className || null,
                        href: parent.href || null,
                        dataAttributes: getDataAttributes(parent),
                        ariaAttributes: getAriaAttributes(parent)
                    });
                    parent = parent.parentElement;
                }

                const selectionData = {
                    text: selectedText,
                    textLength: selectedText.length,
                    element: {
                        tagName: element.tagName,
                        id: element.id || null,
                        className: element.className || null,
                        href: element.href || null,
                        src: element.src || null,
                        textContent: element.textContent?.substring(0, 200) || null,
                        dataAttributes: getDataAttributes(element),
                        ariaAttributes: getAriaAttributes(element)
                    },
                    // Selectors for reliably finding this element later
                    selectors: {
                        css: generateCSSSelector(element),
                        xpath: generateXPath(element)
                    },
                    parentChain: parentChain,
                    url: window.location.href,
                    // Get selection position
                    rect: range.getBoundingClientRect() ? {
                        x: Math.round(range.getBoundingClientRect().x),
                        y: Math.round(range.getBoundingClientRect().y),
                        width: Math.round(range.getBoundingClientRect().width),
                        height: Math.round(range.getBoundingClientRect().height)
                    } : null
                };
                console.log('SELECTION_EVENT:', JSON.stringify(selectionData));
            }
        }
    }, 300); // Wait 300ms after last change before logging
}, true);
"""


class WebActionRecorder:
    """
    Records user actions (clicks, inputs, selections) in a browser session.

    This class manages a Playwright browser instance and injects JavaScript
    to track user interactions. Events are logged with timestamps and can
    be saved to JSON files.

    Attributes:
        events: List of recorded events with timestamps
        browser: Playwright browser instance (if active)
        page: Current browser page (if active)
        verbose: Whether to print events to console as they occur
    """

    def __init__(self, verbose: bool = True):
        """
        Initialize the recorder.

        Args:
            verbose: If True, print events to console as they're captured
        """
        self.events: List[Dict[str, Any]] = []
        self.browser: Optional["Browser"] = None
        self.page: Optional["Page"] = None
        self.verbose = verbose
        self._playwright = None
        self._cleanup_called = False

    def add_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Add an event with timestamp to the log.

        Args:
            event_type: Type of event ('click', 'input', 'selection')
            event_data: Event data dictionary
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            **event_data
        }
        self.events.append(log_entry)

        if self.verbose:
            self._print_event(event_type, event_data)

    def _print_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Print event information to console."""
        if event_type == 'click':
            print(f"\n[CLICK] {event_data['target']['tagName']} at ({event_data['x']}, {event_data['y']}) - {event_data['url']}")
        elif event_type == 'input':
            target_info = f"{event_data['target']['tagName']}"
            if event_data['target']['id']:
                target_info += f"#{event_data['target']['id']}"
            if event_data['target']['name']:
                target_info += f" (name={event_data['target']['name']})"
            value_preview = event_data['value'][:50] + ('...' if len(event_data['value']) > 50 else '')
            print(f"[INPUT] {target_info} - Value: '{value_preview}'")
        elif event_type == 'selection':
            element_info = f"{event_data['element']['tagName']}"
            if event_data['element']['id']:
                element_info += f"#{event_data['element']['id']}"
            if event_data['element']['className']:
                element_info += f".{event_data['element']['className']}"
            text_preview = event_data['text'][:100] + ('...' if len(event_data['text']) > 100 else '')
            print(f"\n[SELECTION] {element_info} - Text: '{text_preview}'")

    def start(self, url: str = "https://www.google.com", headless: bool = False) -> None:
        """
        Start the browser and begin tracking.

        Args:
            url: Initial URL to navigate to
            headless: Whether to run browser in headless mode

        Raises:
            ImportError: If playwright is not installed
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "The web action recorder requires playwright. "
                "Install it with: pip install 'hivetracered[web]'"
            )

        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=headless)
        self.page = self.browser.new_page()

        # Add all tracking scripts
        self.page.add_init_script(CLICK_TRACKER_SCRIPT)
        self.page.add_init_script(INPUT_TRACKER_SCRIPT)
        self.page.add_init_script(SELECTION_TRACKER_SCRIPT)

        # Set up console message handler
        self.page.on("console", self._handle_console)

        # Navigate to URL
        self.page.goto(url)

        if self.verbose:
            print(f'Browser opened at {url}')
            print('Event tracking is active!')
            print('Tracking: clicks, text input values, and text selections')

    def _handle_console(self, msg) -> None:
        """Parse and log events from browser console."""
        try:
            if msg.text.startswith('CLICK_EVENT:'):
                click_data = json.loads(msg.text[len('CLICK_EVENT:'):])
                self.add_event('click', click_data)
            elif msg.text.startswith('INPUT_EVENT:'):
                input_data = json.loads(msg.text[len('INPUT_EVENT:'):])
                self.add_event('input', input_data)
            elif msg.text.startswith('SELECTION_EVENT:'):
                selection_data = json.loads(msg.text[len('SELECTION_EVENT:'):])
                self.add_event('selection', selection_data)
        except json.JSONDecodeError:
            pass

    def stop(self) -> None:
        """Stop tracking and close the browser."""
        if not self._cleanup_called:
            self._cleanup_called = True
            if self.browser:
                self.browser.close()
            if self._playwright:
                self._playwright.stop()

    def save_to_file(self, filepath: Optional[str] = None) -> str:
        """
        Save all events to a JSON file.

        Args:
            filepath: Path to save file. If None, generates timestamped filename.

        Returns:
            Path to the saved file
        """
        if not self.events:
            if self.verbose:
                print('\nNo events to save')
            return ""

        if filepath is None:
            filepath = f"event_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            json.dump(self.events, f, indent=2)

        if self.verbose:
            print(f'\nEvent log saved to {filepath}')
            self._print_summary()

        return str(filepath)

    def _print_summary(self) -> None:
        """Print summary of recorded events."""
        click_count = sum(1 for e in self.events if e['event_type'] == 'click')
        input_count = sum(1 for e in self.events if e['event_type'] == 'input')
        selection_count = sum(1 for e in self.events if e['event_type'] == 'selection')
        print(f'Total events logged: {len(self.events)} (Clicks: {click_count}, Inputs: {input_count}, Selections: {selection_count})')

    def get_events(self) -> List[Dict[str, Any]]:
        """
        Get all recorded events.

        Returns:
            List of event dictionaries
        """
        return self.events.copy()

    def clear_events(self) -> None:
        """Clear all recorded events."""
        self.events.clear()


def record_browser_session(
    url: str = "https://www.google.com",
    output_file: Optional[str] = None,
    headless: bool = False,
    verbose: bool = True
) -> str:
    """
    Record a browser session until interrupted.

    This is a convenience function that starts a recorder, waits for user
    interaction, and saves the log when interrupted (Ctrl-C).

    Args:
        url: URL to start browsing from
        output_file: Path to save event log (auto-generated if None)
        headless: Whether to run browser in headless mode
        verbose: Whether to print events to console

    Returns:
        Path to the saved event log file
    """
    recorder = WebActionRecorder(verbose=verbose)

    def cleanup(_sig=None, _frame=None):
        """Cleanup handler for graceful shutdown."""
        if verbose:
            print('\nClosing browser...')
        recorder.stop()
        filepath = recorder.save_to_file(output_file)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)

    recorder.start(url=url, headless=headless)

    if verbose:
        print('Press Ctrl-C to close and save the event log.')

    try:
        # Keep the browser open until interrupted
        while True:
            recorder.page.wait_for_timeout(1000)
    except Exception:
        pass
    finally:
        cleanup()


def main():
    """CLI entry point for the web action recorder."""
    # Check for playwright availability early
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: The web action recorder requires the 'web' extras.", file=sys.stderr)
        print("Install with: pip install 'hivetracered[web]'", file=sys.stderr)
        sys.exit(1)

    import argparse

    parser = argparse.ArgumentParser(
        description='Record user interactions in a web browser',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record session at a specific URL
  hivetracered-recorder --url https://example.com

  # Save to a specific file
  hivetracered-recorder --output my_session.json

  # Run in headless mode
  hivetracered-recorder --url https://example.com --headless
        """
    )

    parser.add_argument(
        '--url',
        default='https://www.google.com',
        help='URL to start browsing from (default: https://www.google.com)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file path for event log (default: auto-generated timestamped file)'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (no visible window)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress console output (quiet mode)'
    )

    args = parser.parse_args()

    try:
        record_browser_session(
            url=args.url,
            output_file=args.output,
            headless=args.headless,
            verbose=not args.quiet
        )
    except KeyboardInterrupt:
        print('\nRecording stopped by user')
        sys.exit(0)


if __name__ == '__main__':
    main()
