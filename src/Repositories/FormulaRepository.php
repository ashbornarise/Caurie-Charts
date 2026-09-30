<?php

namespace Cauri\Repositories;

use Cauri\Core\Config;
use Cauri\Core\Database;

final class FormulaRepository
{
    public function __construct(private Database $db)
    {
    }

    /** Formule en vigueur pour une semaine donnée, complétée par les valeurs par défaut de config/formula.php. */
    public function effectiveFor(string $date): array
    {
        $row = $this->db->one(
            'SELECT version, formula_json FROM formula_versions WHERE effective_from <= ? ORDER BY effective_from DESC, version DESC LIMIT 1',
            [$date]
        );
        $defaults = Config::get('formula');
        if (!$row) {
            return $defaults;
        }
        $stored = json_decode($row['formula_json'], true) ?: [];
        $formula = array_replace_recursive($defaults, $stored);
        $formula['version'] = (int) $row['version'];
        return $formula;
    }

    public function all(): array
    {
        return $this->db->all('SELECT f.*, u.name AS author FROM formula_versions f LEFT JOIN users u ON u.id = f.created_by ORDER BY version DESC');
    }

    public function nextVersion(): int
    {
        return (int) $this->db->value('SELECT COALESCE(MAX(version), 0) + 1 FROM formula_versions');
    }
}
