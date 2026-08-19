// Stage 1 Parser: extract pagination info and company URLs from the screen listing page

// Extract page information
const page_info_text = $('[data-page-info]').text().trim();
const page_match = page_info_text.match(/page (\d+) of (\d+)/i);
const current_page = page_match ? parseInt(page_match[1]) : 1;
const total_pages = page_match ? parseInt(page_match[2]) : 1;

// Extract company URLs from the table
const base_url = 'https://www.screener.in';
const company_links = $('table.data-table tbody tr[data-row-company-id] a[href*="/company/"]');

const company_urls = company_links.toArray().map(link => {
    const href = $(link).attr('href');
    return new URL(href, base_url).href;
});

console.log(`Parsed ${company_urls.length} company URLs from page ${current_page}`);

return {
    company_urls,
    current_page,
    total_pages
};
