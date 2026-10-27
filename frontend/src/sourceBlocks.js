// JobSpy boards that refuse this scraper on every measured run. They stay
// selectable and stay in the default source lists; the badge only says so.
//
// The backend maps the same two blocks to their run error text in
// backend/scraper/sources/jobspy.py (`_KNOWN_BLOCKS`). Change both places together.
export const BLOCKED_BADGE = 'Often blocked'

export const SOURCE_BLOCKS = {
  zip_recruiter: 'ZipRecruiter redirects this scraper to a regional site that it does not read, or refuses its requests.',
  google: 'Google usually returns a JavaScript check page instead of job data, and this scraper cannot read that page.',
}

// Whole search modes whose site refuses this scraper from some networks. The editor shows
// the reason under the mode note; the run then fails with the backend's text
// (backend/scraper/sources/caribbeanjobs.py `CLOUDFLARE_BLOCKED`). Change both places together.
export const MODE_BLOCKS = {
  caribbeanjobs: 'caribbeanjobs.com answers many networks with a Cloudflare challenge, which this scraper does not pass. From such a network every run and Test fails and says so.',
}

// Terms notices for modes that scrape a site which discourages automated access.
export const MODE_TERMS = {
  caribbeanjobs: 'Terms: caribbeanjobs.com challenges automated visitors, so scraping it may break its terms of use. Use at your own risk; see LEGAL_DISCLAIMER.md.',
  creative: 'Terms: Behance, Hollylist and Wana Create publish these APIs for their own sites, not for other clients, and Behance challenges automated visitors. Eluta’s robots.txt disallows its RSS search and its terms forbid storing its content; ArtStation and Work With Indies forbid scraping in their terms. Reading them may break their terms of use. Himalayas allows its public API on condition that applicants go through its job link and the job is credited to Himalayas. Use at your own risk; see LEGAL_DISCLAIMER.md.',
}
