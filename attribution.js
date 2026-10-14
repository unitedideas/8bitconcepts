(function () {
  const key = '8bitconcepts-campaign';
  const fields = ['qc', 'utm_source', 'utm_medium', 'utm_campaign'];
  const current = new URLSearchParams(window.location.search);
  const campaign = new URLSearchParams();
  fields.forEach(function (field) {
    const value = current.get(field);
    if (value && /^[a-zA-Z0-9._:-]{1,120}$/.test(value)) campaign.set(field, value);
  });
  let external = false;
  try {
    const referrer = new URL(document.referrer);
    external = referrer.origin !== window.location.origin;
    const directories = {
      'hypestar.org': 'hypestar',
      'getservices.ai': 'getservices',
      'www.aiagencymap.com': 'aiagencymap',
      'aiagencymap.com': 'aiagencymap'
    };
    if (!campaign.has('utm_source') && directories[referrer.hostname]) {
      campaign.set('utm_source', directories[referrer.hostname]);
      campaign.set('utm_medium', 'referral');
      campaign.set('utm_campaign', 'directory-listing');
    }
  } catch (_) {}
  try {
    if (campaign.toString()) {
      sessionStorage.setItem(key, campaign.toString());
    } else if (external) {
      sessionStorage.removeItem(key);
    } else {
      const saved = new URLSearchParams(sessionStorage.getItem(key) || '');
      fields.forEach(function (field) {
        const value = saved.get(field);
        if (value && /^[a-zA-Z0-9._:-]{1,120}$/.test(value)) campaign.set(field, value);
      });
    }
  } catch (_) {}
  window.eightBitAttribution = campaign;
}());
