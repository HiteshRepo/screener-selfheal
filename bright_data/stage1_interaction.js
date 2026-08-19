// Stage 1: Navigate to screen listing, extract company URLs, trigger reruns for pagination

const base_url = 'https://www.screener.in/screens/3/highest-dividend-yield-shares/';
let url = new URL(input.url);

// Navigate to the page
navigate(url.href);

// Parse the current page to get company URLs and page info
const parsed_data = parse();
const {company_urls, current_page, total_pages} = parsed_data;

console.log(`Current page: ${current_page}, Total pages: ${total_pages}`);
console.log(`Found ${company_urls.length} companies on page ${current_page}`);

// If this is the first run (not a rerun), trigger reruns for all other pages
if (!input.is_rerun && current_page === 1) {
    for (let page = 2; page <= total_pages; page++) {
        const next_page_url = new URL(base_url);
        next_page_url.searchParams.set('page', page.toString());
        rerun_stage({
            url: next_page_url.href,
            is_rerun: true
        });
    }
}

// Collect all company URLs from the current page
for (let company_url of company_urls) {
    next_stage({url: company_url});
}
