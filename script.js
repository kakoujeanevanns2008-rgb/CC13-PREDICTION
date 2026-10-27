(function () {
  'use strict';

  // ================== A REMPLIR ==================
  const CONFIG = {
    SUPABASE_URL: 'https://zavnupwvvkmqorfwixak.supabase.co',
    SUPABASE_ANON_KEY: 'sb_publishable_4Wb51NMc-98l78tF1vqiyA_evUbdALN',
    NOM_CHAINE: 'CC13 Prédiction',
    // Utilisés seulement si la base ne fournit pas de valeur :
    TELEGRAM_PAR_DEFAUT: 'https://t.me/+tFJihalrU54zMDM0
',
    PROMO_PAR_DEFAUT: 'CC13',
    INSCRIPTION_PAR_DEFAUT: 'https://refpa-61799.com/L?tag=d_6260612m_2528c_&site=6260612&ad=2528
'
  };
  // ===============================================

  const $ = (id) => document.getElementById(id);

  function h(tag, props, ...enfants) {
    const el = document.createElement(tag);
    if (props) {
      for (const [k, v] of Object.entries(props)) {
        if (k === 'class') el.className = v;
        else if (k === 'text') el.textContent = v;
        else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
        else el.setAttribute(k, v);
      }
    }
    for (const e of enfants) {
      if (e === null || e === undefined) continue;
      el.append(e.nodeType ? e : document.createTextNode(String(e)));
    }
    return el;
  }

  function urlSure(u, defaut) {
    return typeof u === 'string' && /^https?:\/\//i.test(u) ? u : defaut;
  }

  function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('visible');
    setTimeout(() => t.classList.remove('visible'), 2200);
  }

  async function copier(texte) {
    try {
      await navigator.clipboard.writeText(texte);
    } catch (e) {
      const ta = document.createElement('textarea');
      ta.value = texte;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch (e2) { /* rien */ }
      ta.remove();
    }
    toast('Coupon copié : ' + texte);
  }

  function heure(iso) {
    if (!iso) return '--:--';
    return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  function dateLongue(iso) {
    const d = iso ? new Date(iso + 'T12:00:00') : new Date();
    return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }

  // ---------- Bloc coupon + encart affiliation ----------
  function blocCoupon(row, titre) {
    const promo = row.promo_code || CONFIG.PROMO_PAR_DEFAUT;
    const lien = urlSure(row.lien_inscription, CONFIG.INSCRIPTION_PAR_DEFAUT);

    const bloc = h('div', { class: 'coupon-bloc' });
    if (titre) {
      bloc.append(h('h3', { text: titre }), h('p', { class: 'coupon-sous', text: row.match_name }));
    }
    if (row.coupon_code) {
      bloc.append(
        h('div', { class: 'code', text: row.coupon_code }),
        h('button', { class: 'btn btn-coupon', type: 'button', onclick: () => copier(row.coupon_code) },
          'Copier le coupon 1xBet')
      );
    } else {
      bloc.append(h('div', { class: 'code-indispo', text: "Le code coupon n'a pas pu être généré pour ce match aujourd'hui." }));
    }
    bloc.append(
      h('div', { class: 'promo' },
        'Pas encore de compte ? Inscrivez-vous sur 1xBet avec le code promo ',
        h('strong', { text: promo }),
        ' via ',
        h('a', { href: lien, target: '_blank', rel: 'noopener sponsored' }, 'ce lien'),
        ' pour doubler votre premier dépôt !')
    );
    return bloc;
  }

  // ---------- Modal ----------
  function badgesForme(chaine) {
    const conteneur = h('div', { class: 'badges' });
    if (!chaine || chaine === 'N/D') {
      conteneur.append(h('span', { text: 'N/D' }));
      return conteneur;
    }
    chaine.split(' ').forEach((l) => {
      const cls = ['V', 'N', 'D'].includes(l) ? l : '';
      conteneur.append(h('span', { class: 'badge ' + cls, text: l }));
    });
    return conteneur;
  }

  function ouvrirModal(row) {
    const s = row.stats || {};
    const c = $('modal-contenu');
    c.replaceChildren();

    c.append(
      h('h3', { id: 'modal-titre', text: row.match_name }),
      h('p', { class: 'ligue', text: (row.league || '') + ' - ' + heure(row.kickoff) }),
      h('p', { class: 'pari', text: 'Pronostic : ' + row.prediction + ' (' + row.confiance + '%)' }),
      h('h4', { text: "Analyse de l'IA" }),
      h('div', { class: 'analyse-texte', text: row.analysis || 'Analyse indisponible.' })
    );

    c.append(
      h('h4', { text: 'Forme des équipes (5 derniers matchs)' }),
      h('div', { class: 'ligne-forme' }, h('span', { text: row.home_team }), badgesForme(s.forme_domicile)),
      h('div', { class: 'ligne-forme' }, h('span', { text: row.away_team }), badgesForme(s.forme_exterieur))
    );

    c.append(
      h('h4', { text: 'Classement' }),
      h('ul', { class: 'liste' },
        h('li', null, h('span', { text: row.home_team }), h('span', { text: s.classement_domicile || 'N/D' })),
        h('li', null, h('span', { text: row.away_team }), h('span', { text: s.classement_exterieur || 'N/D' })))
    );

    const h2h = Array.isArray(s.h2h) ? s.h2h : [];
    const liste = h('ul', { class: 'liste' });
    if (h2h.length) {
      h2h.forEach((m) => liste.append(
        h('li', null, h('span', { text: m.date + ' - ' + m.match }), h('b', { text: m.score }))));
    } else {
      liste.append(h('li', { text: 'Aucun face-à-face disponible.' }));
    }
    c.append(h('h4', { text: 'Derniers face-à-face' }), liste);

    if (s.probas && s.probas.domicile) {
      c.append(
        h('h4', { text: "Probabilités (source API-Football)" }),
        h('div', { class: 'probas' },
          h('div', null, 'Domicile', h('b', { text: s.probas.domicile })),
          h('div', null, 'Nul', h('b', { text: s.probas.nul })),
          h('div', null, 'Extérieur', h('b', { text: s.probas.exterieur })))
      );
    }

    c.append(blocCoupon(row, 'Coupon 1xBet'));

    $('modal').hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function fermerModal() {
    $('modal').hidden = true;
    document.body.style.overflow = '';
  }

  // ---------- Tableau ----------
  function rendreTableau(rows) {
    const zone = $('pronos');
    zone.replaceChildren();

    const tbody = h('tbody');
    rows.forEach((row) => {
      const tr = h('tr');
      tr.append(
        h('td', { 'data-label': 'Heure', text: heure(row.kickoff) }),
        h('td', { 'data-label': 'Match' },
          h('div', { class: 'match-nom', text: row.match_name }),
          h('div', { class: 'ligue', text: row.league || '' })),
        h('td', { 'data-label': 'Prédiction' }, h('span', { class: 'pari', text: row.prediction })),
        h('td', { 'data-label': 'Confiance' },
          h('div', null,
            h('span', { class: 'pourcent', text: row.confiance + '%' }),
            h('div', { class: 'barre' }, h('span', { style: 'width:' + Number(row.confiance) + '%' })))),
        h('td', { class: 'cellule-bouton' },
          h('button', { class: 'btn btn-analyse', type: 'button', onclick: () => ouvrirModal(row) },
            "Voir l'analyse et les statistiques basiques"))
      );
      tbody.append(tr);
    });

    const thead = h('thead', null, h('tr', null,
      h('th', { text: 'Heure' }), h('th', { text: 'Match' }), h('th', { text: 'Prédiction' }),
      h('th', { text: 'Confiance' }), h('th', { text: '' })));

    zone.append(h('table', { class: 'tableau' }, thead, tbody));
  }

  // ---------- Chargement Supabase ----------
  async function charger() {
    $('date-jour').textContent = dateLongue();
    const telegramLien = $('telegram-btn');
    telegramLien.href = urlSure(CONFIG.TELEGRAM_PAR_DEFAUT, '#');
    $('telegram-texte').textContent = 'Rejoindre notre chaîne ' + CONFIG.NOM_CHAINE + ' sur Telegram';

    try {
      const url = CONFIG.SUPABASE_URL + '/rest/v1/pronostics?select=*&order=date_match.desc,confiance.desc&limit=12';
      const rep = await fetch(url, {
        headers: {
          apikey: CONFIG.SUPABASE_ANON_KEY,
          Authorization: 'Bearer ' + CONFIG.SUPABASE_ANON_KEY
        }
      });
      if (!rep.ok) throw new Error('HTTP ' + rep.status);
      const data = await rep.json();

      if (!data.length) {
        $('pronos').replaceChildren(h('p', { class: 'vide', text: "Pas encore de pronostics. Revenez demain matin après 5h !" }));
        return;
      }

      const dernier = data[0].date_match;
      const rows = data.filter((r) => r.date_match === dernier);
      $('date-jour').textContent = dateLongue(dernier);

      if (rows[0].lien_telegram) telegramLien.href = urlSure(rows[0].lien_telegram, telegramLien.href);

      rendreTableau(rows);
      $('coupon-zone').replaceChildren(blocCoupon(rows[0], 'Coupon du match phare'));
    } catch (e) {
      console.error(e);
      $('pronos').replaceChildren(h('p', { class: 'vide', text: 'Impossible de charger les pronostics pour le moment. Réessayez plus tard.' }));
    }
  }

  $('modal-fermer').addEventListener('click', fermerModal);
  $('modal-fond').addEventListener('click', fermerModal);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') fermerModal(); });

  charger();
})();

