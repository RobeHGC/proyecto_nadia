"""
Review Workflow UI Tests for NADIA

This module tests the complete review workflow using Puppeteer MCP,
including review selection, approval, editing, and batch operations.
"""
import pytest
import asyncio
from typing import Dict, List

from .page_objects.dashboard_page import DashboardPage
from .page_objects.review_page import ReviewPage


class TestReviewWorkflow:
    """Test suite for review workflow functionality."""
    
    @pytest.mark.asyncio
    async def test_review_selection(self, authenticated_dashboard):
        """Test selecting individual reviews."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        # Get available reviews
        review_count = await review_page.get_review_count()
        
        if review_count == 0:
            pytest.skip("No reviews available for testing")
        
        # Select first review
        success = await review_page.select_review(index=0)
        assert success, "Failed to select first review"
        
        # Verify review is selected
        selected_id = await review_page.get_selected_review_id()
        assert selected_id is not None, "No review selected after selection"
        
        # Get review details
        details = await review_page.get_review_details()
        assert details, "Failed to get review details"
        assert 'user_message' in details, "Review should have user message"
        
        print(f"Selected review {selected_id} with message: {details.get('user_message', '')[:50]}...")
    
    @pytest.mark.asyncio
    async def test_review_approval_workflow(self, authenticated_dashboard):
        """Test the complete review approval workflow."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        # Get initial review count
        initial_count = await review_page.get_review_count()
        
        if initial_count == 0:
            pytest.skip("No reviews available for approval testing")
        
        # Select first review
        await review_page.select_review(index=0)
        selected_id = await review_page.get_selected_review_id()
        
        # Get review details before approval
        details_before = await review_page.get_review_details()
        
        # Approve the review
        approval_success = await review_page.approve_review(wait_for_completion=True)
        assert approval_success, "Failed to approve review"
        
        # Verify review was processed (should disappear from queue)
        await asyncio.sleep(2)  # Allow time for UI update
        
        # Check if review count decreased or review is no longer selected
        final_count = await review_page.get_review_count()
        current_selected = await review_page.get_selected_review_id()
        
        # Either count decreased or different review is selected
        review_processed = (final_count < initial_count) or (current_selected != selected_id)
        assert review_processed, "Review was not processed after approval"
        
        print(f"Successfully approved review. Count: {initial_count} -> {final_count}")
    
    @pytest.mark.asyncio
    async def test_review_editing_workflow(self, authenticated_dashboard):
        """Test editing review responses."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for editing testing")
        
        # Select first review
        await review_page.select_review(index=0)
        
        # Enter edit mode
        edit_success = await review_page.enter_edit_mode()
        assert edit_success, "Failed to enter edit mode"
        
        # Edit the response
        new_response = "This is a test edit from automated UI testing."
        edit_response_success = await review_page.edit_review_response(new_response, save=False)
        assert edit_response_success, "Failed to edit response text"
        
        # Add reviewer notes
        notes = "Automated test - edited response for testing purposes"
        notes_success = await review_page.add_reviewer_notes(notes, save=False)
        
        # Set quality score if available
        score_success = await review_page.set_quality_score(4, save=False)
        
        # Save the edit
        save_success = await review_page.save_edit()
        assert save_success, "Failed to save edit"
        
        print(f"Successfully edited review - Response: {edit_response_success}, Notes: {notes_success}, Score: {score_success}")
    
    @pytest.mark.asyncio
    async def test_review_edit_cancellation(self, authenticated_dashboard):
        """Test cancelling review edits."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for edit cancellation testing")
        
        # Select first review
        await review_page.select_review(index=0)
        
        # Get original details
        original_details = await review_page.get_review_details()
        
        # Enter edit mode
        edit_success = await review_page.enter_edit_mode()
        assert edit_success, "Failed to enter edit mode"
        
        # Make some changes
        await review_page.edit_review_response("This should be cancelled", save=False)
        
        # Cancel the edit
        cancel_success = await review_page.cancel_edit()
        assert cancel_success, "Failed to cancel edit"
        
        # Verify changes were not saved (this would require checking the UI state)
        print("Successfully cancelled edit operation")
    
    @pytest.mark.asyncio
    async def test_keyboard_shortcuts(self, authenticated_dashboard):
        """Test keyboard shortcuts for review operations."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for keyboard shortcut testing")
        
        # Select first review
        await review_page.select_review(index=0)
        
        # Test edit shortcut
        edit_shortcut_success = await review_page.use_keyboard_shortcuts('edit')
        
        # Test cancel shortcut
        cancel_shortcut_success = await review_page.use_keyboard_shortcuts('cancel')
        
        # Test navigation shortcuts
        next_shortcut_success = await review_page.use_keyboard_shortcuts('next')
        prev_shortcut_success = await review_page.use_keyboard_shortcuts('previous')
        
        print(f"Keyboard shortcuts - Edit: {edit_shortcut_success}, Cancel: {cancel_shortcut_success}, Navigation: {next_shortcut_success}/{prev_shortcut_success}")
    
    @pytest.mark.asyncio
    async def test_batch_operations(self, authenticated_dashboard):
        """Test batch approval/rejection of multiple reviews."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        review_count = await review_page.get_review_count()
        
        if review_count < 2:
            pytest.skip("Need at least 2 reviews for batch operation testing")
        
        # Select multiple reviews (up to 3 for testing)
        select_count = min(3, review_count)
        
        # Try selecting specific reviews
        reviews = await review_page.get_review_statistics()
        
        # Select first few reviews
        selection_success = await review_page.select_multiple_reviews(
            select_all=False
        )
        
        # Get selected count
        selected_count = await review_page.get_selected_review_count()
        
        if selected_count > 0:
            # Test batch approval
            batch_approve_success = await review_page.batch_approve_selected()
            
            print(f"Batch operations - Selected: {selected_count}, Batch approve: {batch_approve_success}")
        else:
            print("No reviews could be selected for batch operations")
    
    @pytest.mark.asyncio
    async def test_select_all_functionality(self, authenticated_dashboard):
        """Test select all checkbox functionality."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        review_count = await review_page.get_review_count()
        
        if review_count == 0:
            pytest.skip("No reviews available for select all testing")
        
        # Test select all
        select_all_success = await review_page.select_multiple_reviews(select_all=True)
        
        if select_all_success:
            # Check how many are selected
            selected_count = await review_page.get_selected_review_count()
            
            # Clear all selections
            clear_success = await review_page.clear_all_selections()
            
            # Verify cleared
            cleared_count = await review_page.get_selected_review_count()
            
            print(f"Select all test - Total: {review_count}, Selected: {selected_count}, Cleared: {cleared_count}")
            
            assert cleared_count == 0, "Failed to clear all selections"
        else:
            print("Select all functionality not available")


class TestReviewInterface:
    """Test suite for review interface elements."""
    
    @pytest.mark.asyncio
    async def test_review_details_display(self, authenticated_dashboard):
        """Test that review details are properly displayed."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for details testing")
        
        # Select first review
        await review_page.select_review(index=0)
        
        # Get review details
        details = await review_page.get_review_details()
        
        # Verify expected fields are present
        expected_fields = ['user_message', 'ai_response']
        for field in expected_fields:
            if field in details:
                assert details[field], f"Field '{field}' should not be empty"
        
        # Test that details contain reasonable content
        if 'user_message' in details:
            assert len(details['user_message']) > 0, "User message should not be empty"
        
        print(f"Review details: {list(details.keys())}")
    
    @pytest.mark.asyncio
    async def test_review_actions_availability(self, authenticated_dashboard):
        """Test that review action buttons are available when expected."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for action button testing")
        
        # Select first review
        await review_page.select_review(index=0)
        
        # Check availability of action buttons
        actions = {
            'approve': await review_page.is_element_visible(review_page.APPROVE_BUTTON),
            'reject': await review_page.is_element_visible(review_page.REJECT_BUTTON),
            'edit': await review_page.is_element_visible(review_page.EDIT_BUTTON)
        }
        
        # At least approve action should be available
        assert actions['approve'], "Approve button should be visible for selected review"
        
        print(f"Available actions: {[action for action, available in actions.items() if available]}")
    
    @pytest.mark.asyncio
    async def test_review_statistics_display(self, authenticated_dashboard):
        """Test that review statistics are displayed correctly."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        # Get review statistics
        stats = await review_page.get_review_statistics()
        
        # Verify statistics structure
        assert isinstance(stats, dict), "Review statistics should be a dictionary"
        assert 'total' in stats, "Statistics should include total count"
        assert stats['total'] >= 0, "Total count should be non-negative"
        
        print(f"Review statistics: {stats}")


class TestReviewWorkflowEdgeCases:
    """Test edge cases and error conditions in review workflow."""
    
    @pytest.mark.asyncio
    async def test_empty_review_queue(self, authenticated_dashboard):
        """Test behavior when no reviews are available."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        review_count = await review_page.get_review_count()
        
        if review_count > 0:
            print(f"Reviews available ({review_count}) - cannot test empty queue")
            return
        
        # Test that empty state is handled gracefully
        empty_state_elements = [
            ".empty-reviews",
            "[data-testid='no-reviews']",
            ".no-content"
        ]
        
        has_empty_state = False
        for selector in empty_state_elements:
            if await review_page.is_element_visible(selector):
                has_empty_state = True
                break
        
        # Either should show empty state or handle gracefully
        print(f"Empty queue handling - Empty state shown: {has_empty_state}")
    
    @pytest.mark.asyncio
    async def test_rapid_operations(self, authenticated_dashboard):
        """Test rapid consecutive operations don't break the interface."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() < 2:
            pytest.skip("Need at least 2 reviews for rapid operation testing")
        
        # Rapidly select different reviews
        for i in range(min(3, await review_page.get_review_count())):
            await review_page.select_review(index=i)
            await asyncio.sleep(0.1)  # Very short delay
        
        # Verify interface is still responsive
        final_selection = await review_page.get_selected_review_id()
        
        # Should have a valid selection
        assert final_selection is not None, "Interface should remain responsive after rapid operations"
        
        print("Rapid operations test completed successfully")
    
    @pytest.mark.asyncio
    async def test_concurrent_edit_protection(self, authenticated_dashboard):
        """Test behavior when trying to edit while already in edit mode."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for concurrent edit testing")
        
        # Select first review
        await review_page.select_review(index=0)
        
        # Enter edit mode
        first_edit = await review_page.enter_edit_mode()
        assert first_edit, "Failed to enter edit mode initially"
        
        # Try to enter edit mode again
        second_edit = await review_page.enter_edit_mode()
        
        # Should either succeed (no-op) or fail gracefully
        print(f"Concurrent edit protection - Second edit attempt: {second_edit}")
        
        # Cancel any edit mode
        await review_page.cancel_edit()
        
        print("Concurrent edit protection test completed")