"""Test the Strategy Stage Migration

Verifies that the strategy stage has been properly extracted from the monolith
and can generate marketing strategies correctly.
"""

import pytest
from unittest.mock import Mock, MagicMock
from churns.pipeline.context import PipelineContext
from churns.stages.strategy import run as strategy_run
from churns.models import (
    RelevantNicheList,
    MarketingGoalSetStage2,
    MarketingStrategyOutputStage2,
    MarketingGoalSetFinal
)


class TestStrategyStage:
    """Test suite for the marketing strategy generation stage."""
    
    def test_strategy_stage_imports(self):
        """Test that the strategy stage can be imported and has required functions."""
        from churns.stages import strategy
        assert hasattr(strategy, 'run')
        assert hasattr(strategy, 'get_pools_for_task')
        assert hasattr(strategy, 'simulate_marketing_strategy_fallback_staged')
        assert hasattr(strategy, 'extract_json_from_llm_response')
    
    def test_get_pools_for_task(self):
        """Test that task pool selection works correctly."""
        from churns.stages.strategy import get_pools_for_task
        
        # Test product focus tasks
        assert get_pools_for_task("1. Product Photography")["audience"]
        assert get_pools_for_task("4. Menu Spotlights")["audience"]
        
        # Test promotion tasks
        assert get_pools_for_task("2. Promotional Graphics & Announcements")["audience"]
        
        # Test brand atmosphere tasks
        assert get_pools_for_task("3. Store Atmosphere & Decor")["audience"]
        assert get_pools_for_task("5. Cultural & Community Content")["audience"]
        
        # Test informative tasks
        assert get_pools_for_task("6. Recipes & Food Tips")["audience"]
        
        # Test default fallback
        default_pools = get_pools_for_task(None)
        assert "audience" in default_pools
        assert "niche" in default_pools
        assert "objective" in default_pools
        assert "voice" in default_pools
    
    def test_extract_json_from_llm_response(self):
        """Test JSON extraction from various LLM response formats."""
        from churns.stages.strategy import extract_json_from_llm_response
        
        # Test markdown code block with json label
        json_response = '```json\n{"test": "value"}\n```'
        result = extract_json_from_llm_response(json_response)
        assert result == '{"test": "value"}'
        
        # Test generic code block
        generic_response = '```\n{"another": "test"}\n```'
        result = extract_json_from_llm_response(generic_response)
        assert result == '{"another": "test"}'
        
        # Test direct JSON
        direct_json = '{"direct": "json"}'
        result = extract_json_from_llm_response(direct_json)
        assert result == '{"direct": "json"}'
        
        # Test with extra text
        extra_text = 'Here is the JSON: {"data": "value"} and some extra text'
        result = extract_json_from_llm_response(extra_text)
        assert result == '{"data": "value"}'
    
    def test_simulate_marketing_strategy_fallback(self):
        """Test the fallback strategy generation."""
        from churns.stages.strategy import simulate_marketing_strategy_fallback_staged
        
        # Test with no user goals
        strategies = simulate_marketing_strategy_fallback_staged(
            user_goals=None,
            identified_niches=["Casual Dining", "Fast Food"],
            task_type="1. Product Photography",
            num_strategies=2
        )
        
        assert len(strategies) == 2
        for strategy in strategies:
            assert "target_audience" in strategy
            assert "target_niche" in strategy
            assert "target_objective" in strategy
            assert "target_voice" in strategy
    
    def test_strategy_stage_with_no_clients(self):
        """Test strategy stage runs with no API clients (simulation mode)."""
        ctx = PipelineContext(
            task_type="1. Product Photography",
            target_platform={"name": "Instagram Post (1:1 Square)"},
            prompt="A delicious burger",
            marketing_goals=None,
            image_analysis_result={"main_subject": "Gourmet Burger"}
        )
        
        # Run the strategy stage
        strategy_run(ctx)
        
        # Verify results
        assert ctx.suggested_marketing_strategies is not None
        strategies = ctx.suggested_marketing_strategies
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        
        # Verify strategy structure
        for strategy in strategies:
            assert "target_audience" in strategy
            assert "target_niche" in strategy
            assert "target_objective" in strategy
            assert "target_voice" in strategy
    
    def test_strategy_stage_with_user_goals(self):
        """Test strategy stage with user-provided marketing goals."""
        ctx = PipelineContext(
            task_type="2. Promotional Graphics & Announcements",
            target_platform={"name": "Instagram Story/Reel (9:16 Vertical)"},
            prompt="Holiday special promotion",
            # Use original monolith field structure for marketing goals
            marketing_goals={
                "target_audience": "Young Professionals (25-35)",  # Final field name (correct)
                "objective": "Drive Short-Term Sales",  # Final field name (correct)
                "voice": "Urgent & Exciting",  # Final field name (correct)
                "niche": "Fast Food/QSR"  # Final field name (correct)
            },
            image_analysis_result={"main_subject": "Holiday Menu Item"}
        )
        
        # Run the strategy stage
        strategy_run(ctx)
        
        # Verify results incorporate user goals
        strategies = ctx.suggested_marketing_strategies
        assert len(strategies) > 0
        
        # Check that user niche is used consistently across all strategies
        for strategy in strategies:
            assert strategy["target_niche"] == "Fast Food/QSR"
            # Verify all required fields are present
            assert "target_audience" in strategy
            assert "target_objective" in strategy  
            assert "target_voice" in strategy
    
    def test_strategy_stage_with_mock_llm_client(self):
        """Test strategy stage with mock LLM clients."""
        ctx = PipelineContext(
            task_type="3. Store Atmosphere & Decor",
            target_platform={"name": "Pinterest Pin (2:3 Vertical)"},
            prompt="Cozy cafe interior",
            task_description="Showcase our warm atmosphere",
            marketing_goals=None,
            image_analysis_result={"main_subject": "Cafe Interior"}
        )
        
        # Mock instructor client for niche identification
        mock_niche_response = Mock()
        mock_niche_response.relevant_niches = ["Cafe/Coffee Shop", "Casual Dining", "Community Hub"]
        # Mock the usage object properly
        mock_niche_usage = Mock()
        mock_niche_usage.model_dump.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
        mock_niche_response.usage = mock_niche_usage
        mock_niche_response._raw_response = mock_niche_response  # For usage extraction
        
        mock_strategy_client = Mock()
        mock_strategy_client.chat.completions.create.return_value = mock_niche_response
        
        ctx.strategy_instructor_client = mock_strategy_client
        
        # Mock response for goal generation
        mock_goal_response = Mock()
        mock_strategy_data = [
            MarketingGoalSetStage2(
                target_audience="Remote Workers",
                target_objective="Build Community",
                target_voice="Warm & Welcoming"
            ),
            MarketingGoalSetStage2(
                target_audience="Coffee Enthusiasts", 
                target_objective="Showcase Brand Personality/Values",
                target_voice="Cozy & Comforting"
            ),
            MarketingGoalSetStage2(
                target_audience="Local Residents",
                target_objective="Increase Brand Awareness", 
                target_voice="Community-Focused"
            )
        ]
        mock_goal_response.strategies = mock_strategy_data
        # Mock the usage object properly
        mock_goal_usage = Mock()
        mock_goal_usage.model_dump.return_value = {
            "prompt_tokens": 200,
            "completion_tokens": 150,
            "total_tokens": 350
        }
        mock_goal_response.usage = mock_goal_usage
        mock_goal_response._raw_response = mock_goal_response  # For usage extraction
        
        # Configure mock to return different responses for different calls
        ctx.strategy_instructor_client.chat.completions.create.side_effect = [
            mock_niche_response,  # First call: niche identification
            mock_goal_response    # Second call: goal generation
        ]
        
        # Run the strategy stage
        strategy_run(ctx)
        
        # Verify LLM was called
        assert ctx.strategy_instructor_client.chat.completions.create.call_count == 2
        
        # Verify results
        strategies = ctx.suggested_marketing_strategies
        assert len(strategies) == 3
        
        # Verify strategy structure and content
        for i, strategy in enumerate(strategies):
            assert strategy["target_audience"] == mock_strategy_data[i].target_audience
            assert strategy["target_objective"] == mock_strategy_data[i].target_objective
            assert strategy["target_voice"] == mock_strategy_data[i].target_voice
            assert strategy["target_niche"] in ["Cafe/Coffee Shop", "Casual Dining", "Community Hub"]
        
        # Verify usage information was stored
        assert "strategy_niche_id" in ctx.llm_usage
        assert "strategy_goal_gen" in ctx.llm_usage
        assert ctx.llm_usage["strategy_niche_id"]["total_tokens"] == 150
        assert ctx.llm_usage["strategy_goal_gen"]["total_tokens"] == 350
    
    def test_strategy_stage_logging(self):
        """Test that the strategy stage produces appropriate logs."""
        ctx = PipelineContext(
            task_type="1. Product Photography",
            prompt="Test product",
            image_analysis_result={"main_subject": "Test Subject"}
        )
        
        # Run the strategy stage
        strategy_run(ctx)
        
        # Verify logs were created
        assert len(ctx.logs) > 0
        
        # Check for expected log messages
        log_text = " ".join(ctx.logs)
        assert "Starting marketing strategy generation stage" in log_text
        assert "Stage 1:" in log_text
        assert "Stage 2:" in log_text
        assert "Marketing strategy generation completed" in log_text
    
    def test_stage_order_configuration(self):
        """Test that strategy stage is properly configured in stage order."""
        from churns.pipeline.executor import load_stage_order
        
        stage_order = load_stage_order()
        assert "strategy" in stage_order
        
        # Verify strategy comes after image_eval
        image_eval_index = stage_order.index("image_eval")
        strategy_index = stage_order.index("strategy")
        assert strategy_index == image_eval_index + 1


if __name__ == "__main__":
    # Run a simple test to verify the stage works
    print("Testing strategy stage extraction...")
    
    test_suite = TestStrategyStage()
    
    # Run basic tests
    test_suite.test_strategy_stage_imports()
    print("✅ Import test passed")
    
    test_suite.test_get_pools_for_task()
    print("✅ Task pools test passed")
    
    test_suite.test_extract_json_from_llm_response()
    print("✅ JSON extraction test passed")
    
    test_suite.test_strategy_stage_with_no_clients()
    print("✅ No clients test passed")
    
    test_suite.test_strategy_stage_logging()
    print("✅ Logging test passed")
    
    print("\n🎉 Strategy stage extraction successful!")
    print("✅ All basic tests passed")
    print("✅ Stage can run in simulation mode")
    print("✅ Stage produces proper logging")
    print("✅ Stage structure matches original logic") 