## ADDED Requirements

### Requirement: Fetch target page HTML via requests
The system SHALL fetch the target URL using `requests.get` (no headless browser) and pass the raw response body to the LLM.

#### Scenario: Successful page fetch
- **WHEN** `analyse_page(target_url)` is called with a valid URL
- **THEN** the module calls `requests.get(target_url)` exactly once and uses the response text as input to the OpenAI API

#### Scenario: Non-200 response is logged and forwarded
- **WHEN** `requests.get` returns a non-200 status code
- **THEN** the module logs a warning at `WARNING` level and still passes the response body to OpenAI (no hard failure on HTTP errors)

### Requirement: Call OpenAI API with HTML and schema context
The system SHALL call the OpenAI API (`gpt-4o` model) with a prompt that includes:
- The fetched HTML (or a truncated prefix if it exceeds a safe token limit)
- The list of canonical schema field names from `data/schema.json`
- A clear instruction asking the model to identify which CSS selectors or structural elements map to each required field and describe what changed

#### Scenario: Prompt contains schema fields
- **WHEN** `analyse_page(target_url)` constructs the OpenAI prompt
- **THEN** every required field name from the canonical schema appears in the prompt text

#### Scenario: Prompt contains fetched HTML
- **WHEN** `analyse_page(target_url)` constructs the OpenAI prompt
- **THEN** the prompt includes a portion of the fetched HTML

### Requirement: Return fix description within 900 characters
The system SHALL return a fix description string of at most 900 characters, truncating the OpenAI response if it exceeds this limit.

#### Scenario: OpenAI returns a short description
- **WHEN** the OpenAI API returns a response of 500 characters
- **THEN** `analyse_page` returns that string unchanged

#### Scenario: OpenAI returns an oversized description
- **WHEN** the OpenAI API returns a response of 1200 characters
- **THEN** `analyse_page` returns a string of exactly 900 characters (truncated)

### Requirement: OpenAI API call is isolated to page_analyser module
The OpenAI SDK import and API invocation SHALL appear only in `src/page_analyser.py`. No other module SHALL import or call the OpenAI client directly.

#### Scenario: No other module imports OpenAI
- **WHEN** the source tree is scanned for `import openai` or `from openai`
- **THEN** only `src/page_analyser.py` contains such an import

### Requirement: OPENAI_API_KEY is read from environment
The system SHALL read the `OPENAI_API_KEY` from `os.environ` at call time and raise a `ConfigurationError` (or equivalent) if the key is absent.

#### Scenario: Missing API key raises error
- **WHEN** `OPENAI_API_KEY` is not set in the environment
- **THEN** `analyse_page` raises an exception with a message indicating the missing key

### Requirement: Tests mock both HTTP and OpenAI calls
Tests for `page_analyser.py` SHALL mock `requests.get` and the OpenAI client. No live API calls SHALL be made during test execution.

#### Scenario: Test suite runs without network access
- **WHEN** `tests/test_page_analyser.py` is executed with both `requests.get` and the OpenAI client patched
- **THEN** all tests pass without making any real HTTP or API requests
