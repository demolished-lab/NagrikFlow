// Minimal en/hi strings. Roadmap graph + Admin desk stay English for now (PENDING).
export type Lang = 'en' | 'hi';

export const STR: Record<Lang, Record<string, string>> = {
  en: {
    appTitle: 'Civic Path Navigator',
    myDashboard: 'My Dashboard', roadmap: 'Udyam Roadmap', admin: 'Admin Desk', logout: 'Logout',
    register: 'Register', login: 'Login',
    have: 'What you hold', brief: 'Your plain-words brief', next: 'Easiest next wins',
    none: "Nothing pending — you're all set.",
    noDocs: 'No verified documents yet — connect DigiLocker below.',
    loading: 'Loading your civic profile…',
    dlTitle: 'Connect DigiLocker', dlBody: 'Consent-based import of your verified documents. You approve on the official site.',
    dlBtn: 'Get consent link', dlOpen: 'Open official consent page',
    tgTitle: 'Telegram alerts', tgBody: 'One bot for everyone; your chat links only to your account via a one-time code.',
    tgBtn: 'Get link code', tgSend: 'Send to our bot (expires in 15 min, single use).',
    admTitle: 'Maps under review', admBuild: 'Build new map (scrape cascade)',
    admVerify: 'Stamp verified', admUnverify: 'Unverify',
    admRecheck: 'Recheck source', admRecheckAll: 'Recheck all sources',
  },
  hi: {
    appTitle: 'सिविक पथ नेविगेटर',
    myDashboard: 'मेरा डैशबोर्ड', roadmap: 'उद्यम रोडमैप', admin: 'प्रशासन डेस्क', logout: 'लॉगआउट',
    register: 'पंजीकरण', login: 'लॉगिन',
    have: 'आपके पास क्या है', brief: 'सरल शब्दों में सारांश', next: 'सबसे आसान अगले कदम',
    none: 'कुछ बाकी नहीं — सब तैयार है।',
    noDocs: 'अभी कोई सत्यापित दस्तावेज़ नहीं — नीचे DigiLocker जोड़ें।',
    loading: 'आपकी सिविक प्रोफ़ाइल लोड हो रही है…',
    dlTitle: 'DigiLocker जोड़ें', dlBody: 'आपके सत्यापित दस्तावेज़ों का सहमति-आधारित आयात। आप आधिकारिक साइट पर अनुमति देंगे।',
    dlBtn: 'सहमति लिंक लें', dlOpen: 'आधिकारिक सहमति पेज खोलें',
    tgTitle: 'टेलीग्राम अलर्ट', tgBody: 'सबके लिए एक बॉट; आपकी चैट सिर्फ आपके खाते से जुड़ती है।',
    tgBtn: 'लिंक कोड लें', tgSend: 'हमारे बॉट को भेजें (15 मिनट में समाप्त, एक बार)।',
    admTitle: 'समीक्षाधीन नक्शे', admBuild: 'नया नक्शा बनाएं', admVerify: 'सत्यापित मुहर',
    admUnverify: 'असत्यापित करें', admRecheck: 'स्रोत जांचें', admRecheckAll: 'सभी स्रोत जांचें',
  },
};

export function lang(): Lang {
  return (localStorage.getItem('civic_lang') as Lang) === 'hi' ? 'hi' : 'en';
}
export function setLang(l: Lang) {
  localStorage.setItem('civic_lang', l);
  document.documentElement.lang = l === 'hi' ? 'hi' : 'en';
}
