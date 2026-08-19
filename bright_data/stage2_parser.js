// Extract ticker from URL: /company/INFY/consolidated/ → INFY
const urlParts = location.href.replace(/\/$/, '').split('/');
const companyIdx = urlParts.indexOf('company');
const ticker = companyIdx >= 0 ? urlParts[companyIdx + 1] : null;

// Company name
const company_name = $('h1.shrink-text').first().text().trim() || $('h1').first().text().trim();

// Helper: parse a number from text like "4,54,502" or "4.27"
function extractNumber(text) {
    if (!text) return null;
    const match = text.replace(/,/g, '').match(/-?[\d.]+/);
    return match ? parseFloat(match[0]) : null;
}

// Build a map of ratio name → number from #top-ratios
const ratios = {};
$('#top-ratios li').each(function () {
    const name = $(this).find('span.name').text().trim();
    const num  = $(this).find('span.number').first().text().trim();
    if (name && num) ratios[name] = num;
});

const cmp                = extractNumber(ratios['Current Price']);
const market_cap_cr      = extractNumber(ratios['Market Cap']);
const pe_ratio           = extractNumber(ratios['Stock P/E']) || null;
const dividend_yield_pct = extractNumber(ratios['Dividend Yield']) || null;
const roce_pct           = extractNumber(ratios['ROCE']) || null;
const roe_pct            = extractNumber(ratios['ROE']) || null;

// Compounded Sales Growth — take the 3-year figure
let sales_growth_pct = null;
$('table.ranges-table').each(function () {
    const header = $(this).find('th').text().trim();
    if (/Compounded Sales Growth/i.test(header)) {
        $(this).find('tr').each(function () {
            const label = $(this).find('td').first().text().trim();
            if (/3 Years/i.test(label)) {
                sales_growth_pct = extractNumber($(this).find('td').last().text());
                return false;
            }
        });
        return false;
    }
});

return {
    company_name,
    ticker,
    cmp,
    dividend_yield_pct,
    pe_ratio,
    market_cap_cr,
    roce_pct,
    roe_pct,
    sales_growth_pct,
    source_url: location.href,
    scraped_at: new Date().toISOString(),
};
