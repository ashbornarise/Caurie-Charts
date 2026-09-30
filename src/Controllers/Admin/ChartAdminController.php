<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\Config;
use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Repositories\FormulaRepository;
use Cauri\Services\Audit;
use Cauri\Services\Charts\ChartService;
use Cauri\Services\Charts\Flags;
use Cauri\Services\Charts\Period;

/** Classements : consultation des brouillons, signalements, publication, recalcul et formule. */
final class ChartAdminController extends BaseAdminController
{
    public function index(Request $request): Response
    {
        $this->requireUser($request);
        $rows = $this->db->all(
            "SELECT c.code, r.period_type, r.period_key, r.period_start, r.period_end,
                MIN(r.status) AS status, MAX(r.published_at) AS published_at, MAX(r.corrected_at) AS corrected_at,
                MAX(CASE WHEN ct.code = 'prime' THEN r.id END) AS prime_id, MAX(r.is_provisional) AS provisional,
                (SELECT COUNT(*) FROM weekly_scores ws WHERE ws.country_id = c.id AND ws.week_start = r.period_start
                    AND r.period_type = 'week' AND ws.review_status = 'pending' AND ws.score > 0) AS pending
             FROM chart_runs r JOIN countries c ON c.id = r.country_id JOIN chart_types ct ON ct.id = r.chart_type_id
             GROUP BY c.id, c.code, r.period_type, r.period_key, r.period_start, r.period_end
             ORDER BY r.period_end DESC, FIELD(r.period_type, 'week', 'month', 'year'), c.code
             LIMIT 150"
        );
        return $this->admin('charts', ['rows' => $rows, 'countries' => $this->charts->countries()]);
    }

    public function show(Request $request): Response
    {
        $this->requireUser($request);
        $run = $this->charts->runById((int) $request->param('id'), false);
        if (!$run) {
            throw new HttpException(404);
        }
        $siblings = $this->db->all(
            'SELECT r.id, ct.code, ct.name, r.status FROM chart_runs r JOIN chart_types ct ON ct.id = r.chart_type_id
             WHERE r.country_id = ? AND r.period_type = ? AND r.period_key = ? ORDER BY ct.sort_order',
            [$run['country_id'], $run['period_type'], $run['period_key']]
        );
        $flagged = [];
        if ($run['period_type'] === 'week') {
            $flagged = $this->db->all(
                "SELECT ws.*, t.title, t.slug, a.name AS artist_name, tr.decision, tr.reason, u.name AS decided_by
                 FROM weekly_scores ws JOIN tracks t ON t.id = ws.track_id JOIN artists a ON a.id = t.artist_id
                 LEFT JOIN track_reviews tr ON tr.track_id = ws.track_id AND tr.week_start = ws.week_start
                 LEFT JOIN users u ON u.id = tr.user_id
                 WHERE ws.country_id = ? AND ws.week_start = ? AND ws.flags <> '[]'
                 ORDER BY ws.review_status = 'pending' DESC, ws.score DESC",
                [$run['country_id'], $run['period_start']]
            );
        }
        return $this->admin('chart-run', [
            'run'      => $run,
            'entries'  => $this->charts->entries((int) $run['id']),
            'siblings' => $siblings,
            'flagged'  => $flagged,
            'blocking' => Flags::BLOCKING,
            'pending'  => $run['period_type'] === 'week' ? (new ChartService($this->db))->pendingCount((int) $run['country_id'], $run['period_start']) : 0,
        ]);
    }

    /** Valider ou exclure un titre signalé. Jamais de modification de position à la main. */
    public function decide(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $runId = (int) $request->str('run_id');
        try {
            (new ChartService($this->db))->decide((int) $request->str('track_id'), $request->str('week_start'), $request->str('decision'), $request->str('reason'), $this->uid(), $request->ip());
            return $this->back(path("admin/classements/$runId"), 'success', t('admin.decision_saved'));
        } catch (\Throwable $e) {
            return $this->back(path("admin/classements/$runId"), 'error', $e->getMessage());
        }
    }

    public function publish(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $runId = (int) $request->str('run_id');
        try {
            $n = (new ChartService($this->db))->publish($request->str('country'), $request->str('period_type'), $request->str('period_key'), $this->uid(), $request->ip());
            return $this->back(path("admin/classements/$runId"), 'success', t('admin.published', ['n' => $n]));
        } catch (\Throwable $e) {
            return $this->back(path("admin/classements/$runId"), 'error', $e->getMessage());
        }
    }

    /** Recalcule une semaine (après une saisie manuelle, par exemple). Correction motivée si déjà publiée. */
    public function recompute(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $runId = (int) $request->str('run_id');
        $correction = $request->str('correction') ?: null;
        try {
            $service = new ChartService($this->db);
            $period = Period::fromKey($request->str('period_type'), $request->str('period_key'));
            if ($period->type === 'week') {
                $service->computeWeek($request->str('country'), $period->start, $correction, $this->uid());
            } else {
                // Mois et années ne contiennent que des semaines publiées : ils restent publiés
                $service->computeAggregate($request->str('country'), $period, $period->type === 'month' ? $correction : null, $this->uid(), true);
            }
            Audit::log($this->uid(), 'chart.recompute', 'country_period', $request->str('country') . ':' . $period->key, $correction, [], $request->ip());
            return $this->back(path("admin/classements/$runId"), 'success', t('admin.recomputed'));
        } catch (\Throwable $e) {
            return $this->back(path("admin/classements/$runId"), 'error', $e->getMessage());
        }
    }

    public function formula(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $repo = new FormulaRepository($this->db);
        return $this->admin('formula', [
            'versions'  => $repo->all(),
            'current'   => $repo->effectiveFor(date('Y-m-d')),
            'countries' => $this->charts->countries(false),
            'minDate'   => date('Y-m-d', strtotime('+14 days')),
        ]);
    }

    /**
     * Nouvelle version de la formule. Entrée en vigueur au moins deux semaines plus tard
     * (METHODOLOGIE.md, section 8), toujours un lundi.
     */
    public function saveFormula(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $repo = new FormulaRepository($this->db);
        $formula = $repo->effectiveFor(date('Y-m-d'));
        $effective = $request->str('effective_from');
        $note = trim($request->str('note'));
        $errors = [];

        $date = \DateTimeImmutable::createFromFormat('!Y-m-d', $effective);
        if (!$date || $date < new \DateTimeImmutable('+14 days midnight') || $date->format('N') !== '1') {
            $errors[] = t('admin.formula_date_rule');
        }
        if ($note === '') {
            $errors[] = t('admin.formula_note_required');
        }
        foreach (['audio', 'youtube', 'declaration'] as $k) {
            $v = str_replace(',', '.', $request->str("w_$k"));
            if (!is_numeric($v) || $v < 0 || $v > 10) {
                $errors[] = t('admin.formula_weight_invalid', ['name' => $k]);
            } else {
                $formula['weights'][$k] = round((float) $v, 3);
            }
        }
        $countryWeights = [];
        foreach ($this->charts->countries(false) as $c) {
            foreach (['audio', 'youtube'] as $k) {
                $v = str_replace(',', '.', $request->str("cw_{$c['code']}_$k"));
                if ($v !== '') {
                    if (!is_numeric($v) || $v < 0 || $v > 10) {
                        $errors[] = t('admin.formula_weight_invalid', ['name' => "{$c['code']} $k"]);
                    } else {
                        $countryWeights[$c['code']][$k] = round((float) $v, 3);
                    }
                }
            }
        }
        $formula['country_weights'] = $countryWeights;
        foreach (['spike_factor' => [1, 50], 'declaration_tolerance' => [0, 1]] as $k => [$min, $max]) {
            $v = str_replace(',', '.', $request->str($k));
            if (!is_numeric($v) || $v < $min || $v > $max) {
                $errors[] = t('admin.formula_weight_invalid', ['name' => $k]);
            } else {
                $formula['anti_fraud'][$k] = (float) $v;
            }
        }
        if ($errors) {
            return $this->back(path('admin/formule'), 'error', implode(' ', $errors));
        }

        $version = $repo->nextVersion();
        $formula['version'] = $version;
        $this->db->insert('formula_versions', [
            'version'        => $version,
            'formula_json'   => json_encode($formula, JSON_UNESCAPED_UNICODE),
            'effective_from' => $effective,
            'note'           => mb_substr($note, 0, 500),
            'created_by'     => $this->uid(),
        ]);
        Audit::log($this->uid(), 'formula.create', 'formula_version', $version, $note, ['weights' => $formula['weights'], 'effective_from' => $effective], $request->ip());
        return $this->back(path('admin/formule'), 'success', t('admin.formula_saved', ['version' => $version, 'date' => fmt_date($effective)]));
    }
}
