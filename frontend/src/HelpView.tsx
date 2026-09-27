import React from 'react';

type Props = { onBuildPath: () => void };

const FAQ = [
  { q: 'Where do the steps come from?', a: 'A pathway is assembled from pages discovered and fetched from official government sources. Open the source link on a step to check the latest instructions directly.' },
  { q: 'What does “awaiting source review” mean?', a: 'A newly generated pathway is a draft until an administrator reviews and approves it. Drafts can be inspected, but progress tracking stays disabled until approval.' },
  { q: 'Does the app submit an application for me?', a: 'No. Civic Path Navigator is a guide only. You complete forms and payments on the official government portal.' },
  { q: 'Is my progress saved?', a: 'For reviewed pathways, marking a step complete is saved to your account through the Civic Path Navigator service and is available when you sign in again.' },
];

export default function HelpView({ onBuildPath }: Props) {
  return <section className="cv-help-page cv-anim-up">
    <div className="cv-page-heading"><div><span className="cv-eyebrow">SUPPORT & TRUST</span><h1>Help with your pathway</h1><p>Use source links to verify details before taking action.</p></div></div>
    <div className="cv-help-layout">
      <div className="cv-faq-list">{FAQ.map((item, index) => <article className="cv-faq-card" key={item.q}><span className="cv-faq-number">0{index + 1}</span><div><h2>{item.q}</h2><p>{item.a}</p></div></article>)}</div>
      <aside className="cv-help-note"><span className="cv-help-note-icon" aria-hidden="true">i</span><h2>Guidance, not an official decision</h2><p>Rules, eligibility, fees, and required documents can change. Confirm important details with the linked government department before applying.</p><button className="cv-btn cv-btn-indigo" onClick={onBuildPath}>Build a pathway</button></aside>
    </div>
  </section>;
}
