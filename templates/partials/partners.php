<?php
/**
 * Section « Partenaires officiels ». Tant qu'aucun partenaire n'est enregistré,
 * elle invite à le devenir (aucun nom de partenaire inventé).
 * @var array $partners  @var bool $compact  (accueil : lien vers la page complète)
 */
$compact ??= false;
?>
<section class="partners" id="partenaires" aria-labelledby="partners-title">
    <div class="partners__head">
        <div>
            <h2 id="partners-title"><?= e(t('partners.title')) ?></h2>
            <p class="partners__lead"><?= e(t('partners.lead')) ?></p>
        </div>
        <?php if ($compact && $partners): ?><a class="link-arrow" href="<?= path('partenaires') ?>"><?= e(t('partners.all')) ?></a><?php endif; ?>
    </div>
    <ul class="partners__grid">
        <?php foreach ($partners as $p):
            $tag = $p['url'] ? 'a' : 'div';
            $attrs = $p['url'] ? ' href="' . e($p['url']) . '" target="_blank" rel="noopener sponsored"' : '';
        ?>
        <li>
            <<?= $tag ?> class="partner-card"<?= $attrs ?>>
                <?php if ($p['logo_path']): ?>
                <img class="partner-card__logo" src="/media/partners/<?= e(rawurlencode(basename($p['logo_path']))) ?>" alt="<?= e($p['name']) ?>" loading="lazy">
                <?php else: ?>
                <span class="partner-card__name"><?= e($p['name']) ?></span>
                <?php endif; ?>
                <span class="partner-card__tier"><?= e(t('partners.tier_' . $p['tier'])) ?></span>
                <?php if (!$compact && $p['description']): ?><p class="partner-card__desc"><?= e($p['description']) ?></p><?php endif; ?>
            </<?= $tag ?>>
        </li>
        <?php endforeach; ?>
        <li class="<?= $partners ? '' : 'partner-card--span' ?>">
            <div class="partner-card partner-card--invite<?= $partners ? '' : ' partner-card--wide' ?>">
                <div>
                    <span class="partner-card__name"><?= e(t('partners.empty_title')) ?></span>
                    <p class="partner-card__desc"><?= e(t('partners.empty_text')) ?></p>
                </div>
                <a class="button button--small" href="<?= path('contact', ['sujet' => 'partenariat']) ?>"><?= e(t('partners.cta')) ?></a>
            </div>
        </li>
    </ul>
</section>
